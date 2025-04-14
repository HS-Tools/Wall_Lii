import os
import psycopg2
from collections import defaultdict
from dotenv import load_dotenv
from utils.queries import parse_rank_or_player_args
from utils.regions import parse_server
from utils.time_range import TimeRangeHelper
from datetime import timedelta
from psycopg2.extras import RealDictCursor

load_dotenv()

REGIONS = ["NA", "EU", "AP"]

class LeaderboardDB:
    def __init__(self, use_local: bool = False):
        if use_local:
            #TODO implement local db
            pass
        else:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                sslmode="require",
                cursor_factory=RealDictCursor
            )

    def close(self):
        if self.conn:
            self.conn.close()

    def top10(self, region: str = "global", game_mode: str = "0") -> str:
        is_global = region.lower() == "global"
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
                f"{i+1}. {row['player_name']}: {row['rating']} ({row['region']})" if is_global else f"{i+1}. {row['player_name']}: {row['rating']}"
                for i, row in enumerate(results)
            )
        except Exception as e:
            return f"Error fetching leaderboard: {e}"

    def rank(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        try:
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)

            with self.conn.cursor() as cur:
                query = f"""
                    SELECT DISTINCT ON (region)
                        player_name, rating, region, rank
                    FROM leaderboard_snapshots
                    {where_clause}
                    ORDER BY region, snapshot_time DESC
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
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)

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
                    return f"{query_params[0]} has no recorded peak rating"

                return " | ".join(
                    f"{row['player_name']}'s peak rating in {row['region']} this season: {row['rating']} on {row['snapshot_time'].astimezone(TimeRangeHelper.now_la().tzinfo).strftime('%b %d, %Y')}"
                    for row in rows
                )

        except Exception as e:
            return f"Error fetching peak: {e}"
        
    def day(self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0) -> str:
        try:
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)
            start_time = TimeRangeHelper.start_of_day_la(offset)
            end_time = TimeRangeHelper.start_of_day_la(offset - 1)

            with self.conn.cursor() as cur:
                # Use the parsed where_clause and query_params directly
                cur.execute(f"""
                    SELECT rank, rating, player_name, snapshot_time, region
                    FROM leaderboard_snapshots
                    {where_clause}
                    AND snapshot_time >= %s AND snapshot_time < %s
                    ORDER BY snapshot_time ASC;
                """, query_params + (start_time, end_time))
                rows = cur.fetchall()

                if not rows:
                    return f"{query_params[0]} can't be found."
                
                # Group rows by region
                regions = {}
                for row in rows:
                    region = row['region']
                    if region not in regions:
                        regions[region] = []
                    regions[region].append(row)
                
                # Process each region separately
                results = []
                for region, region_rows in regions.items():
                    if len(region_rows) == 1 or len(set([row['rating'] for row in region_rows])) == 1:
                        last_row = region_rows[0]
                        suffix = " that day" if offset > 0 else " today"
                        results.append(f"{last_row['player_name']} is rank {last_row['rank']} in {region} at {last_row['rating']} with no games played{suffix}")
                    else:
                        # Calculate deltas
                        ratings = [row['rating'] for row in region_rows]
                        last_row = region_rows[-1]
                        start_rating, end_rating = ratings[0], ratings[-1]
                        total_delta = end_rating - start_rating
                        deltas = [ratings[i+1] - ratings[i] for i in range(len(ratings)-1) if ratings[i+1] != ratings[i]]
                        deltas_str = ", ".join([f"{'+' if d > 0 else ''}{d}" for d in deltas])

                        player_name = region_rows[0]['player_name']
                        adjective = "climbed" if total_delta >= 0 else "fell"
                        emote = "liiHappyCat" if total_delta >= 0 else "liiCat"
                        results.append(f"{player_name} {adjective} from {start_rating} to {end_rating} ({'+' if total_delta >= 0 else ''}{total_delta}) in {region} over {len(deltas)} games: {deltas_str} {emote}")
                
                # Join results with pipe separator
                return " | ".join(results)

        except Exception as e:
            return f"Error fetching day stats: {e}"
        
    def week(self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0) -> str:
        try:
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)
            start_of_week = TimeRangeHelper.start_of_week_la(offset)
            end_of_week = TimeRangeHelper.start_of_week_la(offset - 1)
            weekday_labels = ["M", "T", "W", "Th", "F", "Sa", "Su"]
            day_boundaries = [start_of_week + timedelta(days=i) for i in range(8)]  # 7 days + 1 for exclusive upper bound

            with self.conn.cursor() as cur:
                # Use the parsed where_clause and query_params directly
                cur.execute(f"""
                    SELECT rank, rating, player_name, snapshot_time, region
                    FROM leaderboard_snapshots
                    {where_clause}
                    AND snapshot_time >= %s AND snapshot_time < %s
                    ORDER BY snapshot_time ASC;
                """, query_params + (start_of_week, end_of_week))
                rows = cur.fetchall()

                if not rows:
                    return f"{query_params[0]} can't be found."
                
                # Group rows by region
                regions = {}
                for row in rows:
                    region = row['region']
                    if region not in regions:
                        regions[region] = []
                    regions[region].append(row)
                
                # Process each region separately
                results = []
                for region, region_rows in regions.items():
                    if len(region_rows) == 1 or len(set([row['rating'] for row in region_rows])) == 1:
                        last_row = region_rows[0]
                        suffix = " last week" if offset > 0 else " this week"
                        results.append(f"{last_row['player_name']} is rank {last_row['rank']} in {region} at {last_row['rating']} with no games played{suffix}")
                    else:
                        # Calculate deltas by day
                        ratings = [row['rating'] for row in region_rows]
                        timestamps = [row['snapshot_time'] for row in region_rows]
                        player_name = region_rows[0]['player_name']
                        start_rating, end_rating = ratings[0], ratings[-1]
                        total_delta = end_rating - start_rating
                        
                        # Calculate deltas by day
                        delta_by_day = defaultdict(int)
                        valid_deltas = 0
                        
                        for i in range(len(ratings) - 1):
                            delta = ratings[i+1] - ratings[i]
                            ts = timestamps[i+1]
                            if delta != 0:
                                for d in range(7):
                                    if day_boundaries[d] <= ts < day_boundaries[d + 1]:
                                        delta_by_day[d] += delta
                                        valid_deltas += 1
                                        break
                        
                        day_deltas_str = ", ".join(
                            f"{weekday_labels[i]}: {'+' if delta_by_day[i] > 0 else ''}{delta_by_day[i]}"
                            for i in range(7) if delta_by_day[i] != 0
                        )
                        
                        # If no day deltas, show a message about no games played
                        if not day_deltas_str:
                            suffix = " last week" if offset > 0 else " this week"
                            results.append(f"{player_name} is rank {region_rows[-1]['rank']} in {region} at {end_rating} with no games played{suffix}")
                        else:
                            suffix = " last week" if offset > 0 else ""
                            adjective = "climbed" if total_delta >= 0 else "fell"
                            emote = "liiHappyCat" if total_delta >= 0 else "liiCat"
                            results.append(f"{player_name} {adjective} from {start_rating} to {end_rating} ({'+' if total_delta >= 0 else ''}{total_delta}) in {region} over {valid_deltas} games{suffix}: {day_deltas_str} {emote}")
                
                # Join results with pipe separator
                return " | ".join(results)

        except Exception as e:
            return f"Error fetching week stats: {e}"

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
    print("Week tests ---------------")
    print(db.week("jeef", "NA", offset=0))  # today's progress
    print(db.week("jeef", "NA", offset=1))  # yesterday's progress
    print(db.week("jeef", offset=0))
    print(db.week("jeef", "afsdfasf"))
    print(db.week("adsfaeafeawfew"))
    print(db.week("lii"))
    print(db.week("lii", offset=1))
    print(db.week("beterbabbit"))

    db.close()