import os
import psycopg2
import asyncio
import boto3
from collections import defaultdict
from dotenv import load_dotenv
import requests
from utils.queries import parse_rank_or_player_args
from utils.regions import parse_server
from utils.time_range import TimeRangeHelper
from datetime import timedelta
from psycopg2.extras import RealDictCursor
from utils.constants import REGIONS, STATS_LIMIT

load_dotenv()


class LeaderboardDB:
    def __init__(self, use_local: bool = False):
        if use_local:
            # TODO implement local db
            pass
        else:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                sslmode="require",
                cursor_factory=RealDictCursor,
            )

            # Configure AWS client for alias table
            aws_kwargs = {
                "region_name": "us-east-1",
                "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            }

            # Initialize DynamoDB resource for alias table
            dynamodb = boto3.resource("dynamodb", **aws_kwargs)
            self.alias_table = dynamodb.Table("player-alias-table")

            # Initialize with empty values that will be populated later
            self.aliases = {}
            self.patch_link = "Currently fetching patch link..."

            # Load aliases synchronously for initial setup
            self._load_aliases_sync()
            self._fetch_patch_link_sync()

    def _load_aliases_sync(self):
        """Load aliases synchronously for initial setup"""
        try:
            response = self.alias_table.scan()
            self.aliases = {
                item["Alias"].lower(): item["PlayerName"].lower()
                for item in response["Items"]
            }
        except Exception as e:
            print(f"Error loading aliases synchronously: {e}")
            self.aliases = {}

    def _fetch_patch_link_sync(self):
        """Fetch patch link synchronously for initial setup"""
        try:
            # URL of the API
            api_url = "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=4"

            # Send a request to fetch the JSON data from the API
            response = requests.get(api_url)

            # Check if the request was successful
            if response.status_code == 200:
                # Parse the JSON response
                data = response.json()

                # Loop through each article in the data
                for article in data:
                    content = article.get("content", "")  # Extract the content field
                    # Check if 'battlegrounds' is mentioned in the content
                    if "battlegrounds" in content.lower():
                        # Extract and print the article's 'defaultUrl'
                        article_url = article.get("defaultUrl")
                        title = article.get("title")
                        self.patch_link = f"{title}: {article_url}"
                        return
        except Exception as e:
            print(f"Error fetching patch link synchronously: {e}")

    def close(self):
        if self.conn:
            self.conn.close()

    async def _load_aliases(self):
        """Load aliases from DynamoDB table"""
        try:
            response = self.alias_table.scan()
            aliases = {
                item["Alias"].lower(): item["PlayerName"].lower()
                for item in response["Items"]
            }
            return aliases
        except Exception as e:
            print(f"Error loading aliases: {e}")
            return {}

    def player_exists(self, name: str, region: str, game_mode: str = "0") -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM leaderboard_snapshots
                WHERE player_name = %s AND region = %s AND game_mode = %s
                LIMIT 1;
            """,
                (name.lower(), region, game_mode),
            )
            return cur.fetchone() is not None

    def top10(self, region: str = "global", game_mode: str = "0") -> str:
        is_global = not parse_server(region)

        if not is_global:
            if parse_server(region) is None:
                return "Invalid region specified. Please use a valid region or no region for global."
            region = parse_server(region) if not is_global else None

        query = """
            WITH latest_snapshots AS (
                SELECT DISTINCT ON (player_name, game_mode, region)
                    player_name,
                    rating,
                    region,
                    snapshot_time
                FROM leaderboard_snapshots
                WHERE game_mode = %s {region_filter}
                ORDER BY player_name, game_mode, region, snapshot_time DESC
            )
            SELECT player_name, rating, region
            FROM latest_snapshots
            ORDER BY rating DESC
            LIMIT 10;
            """

        region_filter = "" if is_global else "AND region = %s"
        query = query.format(region_filter=region_filter)
        query_params = (game_mode,) if is_global else (game_mode, region.upper())
        title = "Top 10 globally: " if is_global else f"Top 10 {region.upper()}: "

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, query_params)
                results = cur.fetchall()

            return title + ", ".join(
                (
                    f"{i+1}. {row['player_name']}: {row['rating']} ({row['region']})"
                    if is_global
                    else f"{i+1}. {row['player_name']}: {row['rating']}"
                )
                for i, row in enumerate(results)
            )
        except Exception as e:
            return f"Error fetching leaderboard: {e}"

    def rank(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        try:
            where_clause, query_params, rank = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=self.conn.cursor(),
            )

            # Determine which table to use based on rank
            table_name = (
                "current_leaderboard"
                if (rank and rank > STATS_LIMIT)
                else "leaderboard_snapshots"
            )
            snapshot_time = (
                ", snapshot_time" if table_name == "leaderboard_snapshots" else ""
            )

            with self.conn.cursor() as cur:
                query = f"""
                    SELECT DISTINCT ON (region)
                        player_name, rating, region, rank
                    FROM {table_name}
                    {where_clause}
                    ORDER BY region{snapshot_time} DESC
                """

                cur.execute(query, query_params)
                rows = cur.fetchall()

                if not rows:
                    return f"{query_params[0].lower()} can't be found."

                return " | ".join(
                    f"{row['player_name']} is rank {row['rank']} in {row['region']} at {row['rating']}"
                    for row in rows
                )

        except Exception as e:
            return f"Error fetching rank: {e}"

    def peak(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        try:
            where_clause, query_params, _ = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=self.conn.cursor(),
            )

            with self.conn.cursor() as cur:
                query = f"""
                    SELECT DISTINCT ON (region)
                        player_name, rating, region, snapshot_time
                    FROM leaderboard_snapshots
                    {where_clause}
                    ORDER BY region, rating DESC, snapshot_time ASC
                """
                cur.execute(query, query_params)
                rows = cur.fetchall()

                if not rows:
                    return f"{query_params[0]} is not in the top {STATS_LIMIT}."

                return " | ".join(
                    f"{row['player_name']}'s peak rating in {row['region']} this season: {row['rating']} on {row['snapshot_time'].astimezone(TimeRangeHelper.now_la().tzinfo).strftime('%b %d, %Y')}"
                    for row in rows
                )

        except Exception as e:
            return f"Error fetching peak: {e}"

    def day(
        self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0
    ) -> str:
        try:
            where_clause, query_params, _ = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=self.conn.cursor(),
            )
            start_time = TimeRangeHelper.start_of_day_la(offset)
            end_time = TimeRangeHelper.start_of_day_la(offset - 1)

            with self.conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT rank, rating, player_name, snapshot_time, region
                    FROM leaderboard_snapshots
                    {where_clause}
                    AND snapshot_time >= %s AND snapshot_time < %s
                    ORDER BY snapshot_time ASC;
                """,
                    query_params + (start_time, end_time),
                )
                rows = cur.fetchall()

            return self._summarize_progress(
                rows, offset, fallback_query=(where_clause, query_params)
            )

        except Exception as e:
            return f"Error fetching day stats: {e}"

    def week(
        self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0
    ) -> str:
        try:
            where_clause, query_params, _ = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=self.conn.cursor(),
            )
            start = TimeRangeHelper.start_of_week_la(offset)
            end = TimeRangeHelper.start_of_week_la(offset - 1)
            labels = ["M", "T", "W", "Th", "F", "Sa", "Su"]
            boundaries = [start + timedelta(days=i) for i in range(8)]

            with self.conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT rank, rating, player_name, snapshot_time, region
                    FROM leaderboard_snapshots
                    {where_clause}
                    AND snapshot_time >= %s AND snapshot_time < %s
                    ORDER BY snapshot_time ASC;
                """,
                    query_params + (start, end),
                )
                rows = cur.fetchall()

            return self._summarize_progress(
                rows,
                offset,
                is_week=True,
                day_boundaries=boundaries,
                labels=labels,
                fallback_query=(where_clause, query_params),
            )

        except Exception as e:
            return f"Error fetching week stats: {e}"

    def _summarize_progress(
        self,
        rows,
        offset,
        is_week=False,
        day_boundaries=None,
        labels=None,
        fallback_query=None,
    ):
        regions = defaultdict(list)
        for row in rows:
            regions[row["region"]].append(row)

        # If no regions and we have a fallback query, fetch latest snapshot
        if not regions and fallback_query:
            where_clause, query_params = fallback_query
            with self.conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (region)
                        rank, rating, player_name, region
                    FROM leaderboard_snapshots
                    {where_clause}
                    ORDER BY region, snapshot_time DESC;
                """,
                    query_params,
                )
                fallback_rows = cur.fetchall()

            if not fallback_rows:
                return f"{query_params[0]} is not in the top {STATS_LIMIT}."

            results = []
            for row in fallback_rows:
                suffix = (
                    " last week"
                    if is_week and offset > 0
                    else (
                        " this week"
                        if is_week
                        else (" that day" if offset > 0 else " today")
                    )
                )
                results.append(
                    f"{row['player_name']} is rank {row['rank']} in {row['region']} at {row['rating']} with no games played{suffix}"
                )
            return " | ".join(results)

        results = []
        for region, region_rows in regions.items():
            ratings = [r["rating"] for r in region_rows]
            timestamps = [r["snapshot_time"] for r in region_rows]
            player_name = region_rows[0]["player_name"]
            rank = region_rows[-1]["rank"]
            start_rating, end_rating = ratings[0], ratings[-1]
            total_delta = end_rating - start_rating

            if len(region_rows) == 1 or len(set(ratings)) <= 1:
                time_suffix = (
                    " last week"
                    if is_week and offset > 0
                    else (
                        " this week"
                        if is_week
                        else (" that day" if offset > 0 else " today")
                    )
                )
                results.append(
                    f"{player_name} is rank {rank} in {region} at {end_rating} with no games played{time_suffix}"
                )
                continue

            adjective = "climbed" if total_delta >= 0 else "fell"
            emote = "liiHappyCat" if total_delta >= 0 else "liiCat"

            if is_week:
                delta_by_day = defaultdict(int)
                delta_count = 0
                for i in range(len(ratings) - 1):
                    delta = ratings[i + 1] - ratings[i]
                    ts = timestamps[i + 1]
                    if delta != 0:
                        for d in range(7):
                            if day_boundaries[d] <= ts < day_boundaries[d + 1]:
                                delta_by_day[d] += delta
                                delta_count += 1
                                break

                day_deltas_str = ", ".join(
                    f"{labels[d]}: {'+' if delta_by_day[d] > 0 else ''}{delta_by_day[d]}"
                    for d in range(7)
                    if delta_by_day[d] != 0
                )

                if not day_deltas_str:
                    suffix = " last week" if offset > 0 else " this week"
                    results.append(
                        f"{player_name} is rank {rank} in {region} at {end_rating} with no games played{suffix}"
                    )
                else:
                    suffix = " last week" if offset > 0 else ""
                    results.append(
                        f"{player_name} {adjective} from {start_rating} to {end_rating} "
                        f"({'+' if total_delta >= 0 else ''}{total_delta}) in {region} over {delta_count} games{suffix}: {day_deltas_str} {emote}"
                    )
            else:
                deltas = [
                    ratings[i + 1] - ratings[i]
                    for i in range(len(ratings) - 1)
                    if ratings[i + 1] != ratings[i]
                ]
                deltas_str = ", ".join([f"{'+' if d > 0 else ''}{d}" for d in deltas])
                results.append(
                    f"{player_name} {adjective} from {start_rating} to {end_rating} "
                    f"({'+' if total_delta >= 0 else ''}{total_delta}) in {region} over {len(deltas)} games: {deltas_str} {emote}"
                )

        return " | ".join(results)

    def milestone(self, milestone_str: str, region: str = None) -> str:
        """
        Get the first player to reach a milestone rating in solo and duos.
        """
        try:
            # Parse milestone
            milestone = (
                int(float(milestone_str[:-1]) * 1000)
                if milestone_str.lower().endswith("k")
                else int(milestone_str)
            )
            milestone = (milestone // 1000) * 1000
            if milestone < 8000:
                return "Milestones start at 8000. Please try a higher value."

            # Validate region
            parsed_region = None
            if region:
                parsed_region = parse_server(region.upper())
                if not parsed_region:
                    return f"Invalid region '{region}'. Please use NA, EU, or AP."

            # Shared query body - use TRIM to fix spacing issues
            base_query = """
                SELECT 
                    m.*,
                    TRIM(to_char(m.timestamp AT TIME ZONE 'America/Los_Angeles', 'Month')) || ' ' || 
                    TRIM(to_char(m.timestamp AT TIME ZONE 'America/Los_Angeles', 'DD HH:MI PM')) as formatted_time
                FROM milestone_tracking m
                WHERE m.season = %s AND m.milestone = %s AND m.game_mode = %s
            """
            if parsed_region:
                base_query += " AND m.region = %s"
            base_query += " ORDER BY m.timestamp ASC LIMIT 1"

            # Execute queries for solo and duos
            with self.conn.cursor() as cur:
                results = []
                for mode in ("0", "1"):
                    params = [14, milestone, mode]
                    if parsed_region:
                        params.append(parsed_region)
                    cur.execute(base_query, params)
                    result = cur.fetchone()
                    if result:
                        prefix = "In Duos: " if mode == "1" else ""
                        response = (
                            f"{prefix}{result['player_name']} was the first to reach {milestone_str} "
                            f"in {result['region']}on {result['formatted_time']} PT"
                        )
                        results.append(response)

            if not results:
                target = f"in {parsed_region}" if parsed_region else "in any region"
                return f"No players have reached {milestone_str} {target} yet."

            return " | ".join(results)

        except ValueError:
            return (
                "Invalid milestone format. Please use a number like '13000' or '13k'."
            )
        except Exception as e:
            return f"Error fetching milestone data: {e}"

    def region_stats(self, region: str = None, game_mode: str = "0") -> str:
        try:
            region = parse_server(region)
            regions = REGIONS if region is None else [region.upper()]
            results = []

            for reg in regions:
                with self.conn.cursor() as cur:
                    # Count the number of players in the region
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT player_name) AS player_count
                        FROM current_leaderboard
                        WHERE region = %s AND game_mode = %s
                    """,
                        (reg, game_mode),
                    )
                    player_count = cur.fetchone()["player_count"]

                    # Calculate the average rating of the top 25 players
                    cur.execute(
                        """
                        SELECT AVG(rating) AS avg_rating
                        FROM (
                            SELECT rating
                            FROM current_leaderboard
                            WHERE region = %s AND game_mode = %s
                            ORDER BY rating DESC
                            LIMIT 25
                        ) AS top_25
                    """,
                        (reg, game_mode),
                    )
                    avg_rating = cur.fetchone()["avg_rating"]

                    results.append(
                        f"{reg} has {player_count} players and Top 25 avg is {int(avg_rating)}"
                    )

            return " | ".join(results)

        except Exception as e:
            return f"Error fetching region stats: {e}"

    async def fetchPatchLink(self):
        # URL of the API
        api_url = "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=4"

        # Send a request to fetch the JSON data from the API
        response = requests.get(api_url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()

            # Loop through each article in the data
            for article in data:
                content = article.get("content", "")  # Extract the content field
                # Check if 'battlegrounds' is mentioned in the content
                if "battlegrounds" in content.lower():
                    # Extract and print the article's 'defaultUrl'
                    article_url = article.get("defaultUrl")
                    title = article.get("title")
                    self.patch_link = f"{title}: {article_url}"
                    return
            else:
                print("Patch link not found")
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")


if __name__ == "__main__":
    db = LeaderboardDB()

    print("Top 10 tests ---------------")
    print(db.top10())  # global
    print(db.top10("NA"))
    print(db.top10("EU", "1"))
    print(db.top10("afsdfasf"))
    print("Rank tests ---------------")
    print(db.rank("lii"))
    print(db.rank("lii", "EU"))
    print(db.rank("1"))
    print(db.rank("1", "NA"))
    print(db.rank("1", "EU", "1"))
    print(db.rank("beterbabbit"))
    print(db.rank("beterbabbit", "NA"))
    print(db.rank("lii", "afsdfasf"))
    print(db.rank("NA", "beterbabbit"))
    print(db.rank("NA", "safdewafzfeafeawfef"))
    print(db.rank("2300"))
    print(db.rank("19000"))
    print("Peak tests ---------------")
    print(db.peak("jeef"))
    print(db.peak("lii", "EU"))
    print(db.peak("1"))
    print(db.peak("1", "NA"))
    print(db.peak("NA", "1"))
    print(db.peak("NA", "jeef"))
    print(db.peak("beterbabbit"))
    print("Day tests ---------------")
    print(db.day("jeef", "NA", offset=0))  # today's progress
    print(db.day("jeef", "NA", offset=1))  # yesterday's progress
    print(db.day("jeef", offset=0))
    print(db.day("jeef", "afsdfasf"))
    print(db.day("adsfaeafeawfew"))
    print(db.day("lii"))
    print(db.day("1", "na"))
    print(db.day("sevel"))
    print(db.day("beterbabbit"))
    print(db.day("beter", "NA"))
    print(db.day("1000"))
    print("Week tests ---------------")
    print(db.week("jeef", "NA", offset=0))  # today's progress
    print(db.week("jeef", "NA", offset=1))  # yesterday's progress
    print(db.week("jeef", offset=0))
    print(db.week("jeef", "afsdfasf"))
    print(db.week("adsfaeafeawfew"))
    print(db.week("lii"))
    print(db.week("lii", offset=1))
    print(db.week("beterbabbit"))
    print(db.week("234324324"))
    print(db.week("900"))
    print(db.week("beter"))

    print("Milestone tests ---------------")
    print(db.milestone("13k"))
    print(db.milestone("13000"))
    print(db.milestone("13k", "NA"))
    print(db.milestone("13k", "EU"))
    print(db.milestone("13k", "AP"))
    print(db.milestone("20k"))
    print(db.milestone("8k"))
    print(db.milestone("7k"))  # Should show error for being too low

    print("Region stats tests ---------------")
    print(db.region_stats())
    print(db.region_stats("NA"))
    print(db.region_stats("EU"))
    print(db.region_stats("AP"))
    print(db.region_stats("NA", "0"))
    print(db.region_stats("EU", "1"))
    print(db.region_stats("AP", "0"))

    db.close()
