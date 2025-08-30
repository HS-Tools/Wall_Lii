import os
import psycopg2
from psycopg2 import pool
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
from utils.constants import NON_CN_REGIONS, REGIONS, STATS_LIMIT
from typing import Optional
import aiohttp

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import SEASON

load_dotenv()

# Table names
CURRENT_LEADERBOARD = "current_leaderboard"
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
MILESTONE_TRACKING = "milestone_tracking"

# New normalized table names (test versions)
from config import TEST_TABLES

DAILY_LEADERBOARD_STATS_TEST = TEST_TABLES["daily_leaderboard_stats"]
LEADERBOARD_SNAPSHOTS_TEST = TEST_TABLES["leaderboard_snapshots"]
PLAYERS_TABLE = TEST_TABLES["players"]


def get_table_name_with_join(
    table_name: str, use_test_tables: bool = True
) -> tuple[str, str]:
    """
    Get the appropriate table name and join clause for the new normalized structure.
    Returns (table_name, join_clause)
    """
    if not use_test_tables:
        return table_name, ""

    if table_name == LEADERBOARD_SNAPSHOTS:
        return (
            LEADERBOARD_SNAPSHOTS_TEST,
            f"INNER JOIN {PLAYERS_TABLE} p ON ls.player_id = p.player_id",
        )
    elif table_name == CURRENT_LEADERBOARD:
        return (
            CURRENT_LEADERBOARD,
            f"INNER JOIN {PLAYERS_TABLE} p ON cl.player_id = p.player_id",
        )
    else:
        return table_name, ""


class LeaderboardDB:
    def __init__(self, use_local: bool = False):
        if use_local:
            # TODO implement local db
            pass
        else:
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
            self._refresh_task: Optional[asyncio.Task] = None

            # Initial sync load
            try:
                loop = asyncio.get_event_loop()
                self.aliases = loop.run_until_complete(self._load_aliases())
                self.patch_link = loop.run_until_complete(self._fetch_patch_link())
                # Start background tasks
                loop.run_until_complete(self.start_background_tasks())
            except RuntimeError:
                # If no event loop is available, fall back to sync methods
                response = self.alias_table.scan()
                self.aliases = {
                    item["Alias"].lower(): item["PlayerName"].lower()
                    for item in response["Items"]
                }
                self.patch_link = requests.get(api_url).json()

    def _get_connection(self):
        if not hasattr(self, "_connection_pool"):
            self._connection_pool = pool.SimpleConnectionPool(
                1,
                10,  # minconn, maxconn
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            )
        return self._connection_pool.getconn()

    async def _fetch_patch_link(self) -> str:
        """Fetch patch link from Supabase news_posts table"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT title, slug, updated_at
                    FROM news_posts
                    WHERE battlegrounds_relevant = true
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """
                )
                rows = cur.fetchall()

                if not rows:
                    return "Currently fetching patch link..."

                links = []
                for row in rows:
                    # Format the date as "Jun 11" format
                    if row["updated_at"]:
                        date_str = row["updated_at"].strftime("%b %d")
                    else:
                        date_str = ""

                    if date_str:
                        links.append(
                            f"{row['title']} ({date_str}) wallii.gg/news/{row['slug']}"
                        )
                    else:
                        links.append(f"{row['title']} wallii.gg/news/{row['slug']}")

                return " | ".join(links)
        except Exception as e:
            print(f"Error fetching patch link: {e}")
            return "Currently fetching patch link..."
        finally:
            self._connection_pool.putconn(conn)

    async def _load_aliases(self) -> dict:
        """Load aliases from DynamoDB table"""
        try:
            response = self.alias_table.scan()
            return {
                item["Alias"].lower(): item["PlayerName"].lower()
                for item in response["Items"]
            }
        except Exception as e:
            print(f"Error loading aliases: {e}")
            return {}

    async def _periodic_refresh(self):
        """Periodically refresh aliases and patch link"""
        while True:
            try:
                # Refresh aliases
                self.aliases = await self._load_aliases()
                print("Refreshed aliases")

                # Refresh patch link
                self.patch_link = await self._fetch_patch_link()
                print("Refreshed patch link")

            except Exception as e:
                print(f"Error in periodic refresh: {e}")

            # Wait for 1 minute before next refresh
            await asyncio.sleep(60)

    def player_exists(self, name: str, region: str, game_mode: str = "0") -> bool:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT 1
                    FROM {LEADERBOARD_SNAPSHOTS_TEST} ls
                    INNER JOIN {PLAYERS_TABLE} p ON ls.player_id = p.player_id
                    WHERE p.player_name = %s AND ls.region = %s AND ls.game_mode = %s
                    LIMIT 1;
                """,
                    (name.lower(), region, game_mode),
                )
                return cur.fetchone() is not None
        finally:
            self._connection_pool.putconn(conn)

    def top10(self, region: str = "global", game_mode: str = "0") -> str:
        """
        Fetch top 10 players using daily_leaderboard_stats.
        If region == "global", get top 10 from each region for today's baseline date, then sort by rating.
        If a specific region is provided, fetch top 10 for that region only.
        """
        conn = self._get_connection()
        try:
            # Determine baseline date as start of current day in LA
            baseline_date = TimeRangeHelper.start_of_day_la(0).date()

            # Check if any entry from today exists
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT 1
                    FROM {DAILY_LEADERBOARD_STATS_TEST}
                    WHERE day_start = %s
                    LIMIT 1;
                """,
                    (baseline_date,),
                )
                if not cur.fetchone():
                    # If no entry from today exists, use yesterday's data
                    baseline_date = baseline_date - timedelta(days=1)

            # Global: collect top 10 from each region, then sort across regions
            if not parse_server(region):
                all_rows = []
                for reg in NON_CN_REGIONS:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            f"""
                            SELECT p.player_name, d.rating, d.rank, d.region
                            FROM {DAILY_LEADERBOARD_STATS_TEST} d
                            INNER JOIN {PLAYERS_TABLE} p ON d.player_id = p.player_id
                            WHERE d.region = %s AND d.game_mode = %s AND d.day_start = %s
                            ORDER BY d.rank ASC
                            LIMIT 10;
                            """,
                            (reg, game_mode, baseline_date),
                        )
                        rows = cur.fetchall()
                        all_rows.extend(rows)

                if not all_rows:
                    return "No leaderboard data available for any region today."

                # Sort combined rows by rating descending and take top 10
                sorted_rows = sorted(all_rows, key=lambda r: r["rating"], reverse=True)[
                    :10
                ]
                # Format output
                output = "Top 10 Global (No CN): " + ", ".join(
                    f"{i+1}. {row['player_name']}: {row['rating']} ({row['region']})"
                    for i, row in enumerate(sorted_rows)
                )
                return output + " | wallii.gg/all"

            # Specific region: validate region code
            parsed_region = parse_server(region)
            if not parsed_region:
                return (
                    "Invalid region specified. Please use NA, EU, AP, CN or 'global'."
                )

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT p.player_name, d.rating, d.rank
                    FROM {DAILY_LEADERBOARD_STATS_TEST} d
                    INNER JOIN {PLAYERS_TABLE} p ON d.player_id = p.player_id
                    WHERE d.region = %s AND d.game_mode = %s AND d.day_start = %s
                    ORDER BY d.rank ASC
                    LIMIT 10;
                    """,
                    (parsed_region, game_mode, baseline_date),
                )
                rows = cur.fetchall()

            if not rows:
                return f"No leaderboard data available for {parsed_region} today."

            output = f"Top 10 {parsed_region}: " + ", ".join(
                f"{i+1}. {row['player_name']}: {row['rating']}"
                for i, row in enumerate(rows)
            )
            return output + f" | wallii.gg/{parsed_region.lower()}"

        except Exception as e:
            return f"Error fetching leaderboard: {e}"
        finally:
            self._connection_pool.putconn(conn)

    def rank(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        conn = self._get_connection()
        try:
            where_clause, query_params, rank, region = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=conn.cursor(cursor_factory=RealDictCursor),
            )

            print(where_clause, query_params, rank, region)

            def fetch_rank(cur, table_name: str) -> list:
                new_table_name, join_clause = get_table_name_with_join(table_name)
                table_alias = (
                    "ls" if new_table_name == LEADERBOARD_SNAPSHOTS_TEST else "cl"
                )

                snapshot_time = (
                    ", ls.snapshot_time"
                    if new_table_name == LEADERBOARD_SNAPSHOTS_TEST
                    else ""
                )
                snapshot_order = (
                    "ls.snapshot_time DESC, "
                    if new_table_name == LEADERBOARD_SNAPSHOTS_TEST
                    else ""
                )

                # For snapshots table, we need to get rank from daily_leaderboard_stats_test
                if new_table_name == LEADERBOARD_SNAPSHOTS_TEST:
                    # First get the player data from snapshots
                    query = f"""
                        SELECT DISTINCT ON (ls.region)
                            p.player_name, ls.rating, ls.region, ls.player_id, ls.game_mode{snapshot_time}
                        FROM {new_table_name} {table_alias}
                        {join_clause}
                        {where_clause}
                        ORDER BY {table_alias}.region, {snapshot_order}ls.rating DESC
                    """
                    cur.execute(query, query_params)
                    rows = cur.fetchall()

                    # Now get the rank for each player from daily_leaderboard_stats_test
                    result_rows = []
                    for row in rows:
                        # Get the latest rank for this player
                        cur.execute(
                            f"""
                            SELECT rank
                            FROM {DAILY_LEADERBOARD_STATS_TEST}
                            WHERE player_id = %s AND region = %s AND game_mode = %s
                            ORDER BY day_start DESC
                            LIMIT 1
                            """,
                            (row["player_id"], row["region"], row["game_mode"]),
                        )
                        rank_result = cur.fetchone()
                        rank = rank_result["rank"] if rank_result else None

                        # Create a new row with the rank
                        result_row = {
                            "player_name": row["player_name"],
                            "rating": row["rating"],
                            "region": row["region"],
                            "rank": rank,
                        }
                        if "snapshot_time" in row:
                            result_row["snapshot_time"] = row["snapshot_time"]
                        result_rows.append(result_row)

                    return result_rows
                else:
                    # For current_leaderboard, use the old structure without joins
                    query = f"""
                        SELECT DISTINCT ON (region)
                            player_name, rating, region, rank{snapshot_time}
                        FROM {new_table_name}
                        {where_clause.replace('p.player_name', 'player_name').replace('ls.game_mode', 'game_mode').replace('ls.region', 'region')}
                        ORDER BY region, {snapshot_order}rank DESC
                    """
                    cur.execute(query, query_params)
                    return cur.fetchall()

            # Handle rank-based lookup
            if rank is not None:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if region:
                        # Only query specified region
                        if rank > 1000:
                            # Use current_leaderboard for ranks > 1000
                            cur.execute(
                                f"""
                                SELECT player_name, rating, region, rank
                                FROM {CURRENT_LEADERBOARD}
                                WHERE rank = %s AND region = %s AND game_mode = %s
                                LIMIT 1;
                                """,
                                (rank, region, game_mode),
                            )
                        else:
                            # Use daily_leaderboard_stats_test for ranks <= 1000
                            cur.execute(
                                f"""
                                SELECT p.player_name, d.rating, d.region, d.rank
                                FROM {DAILY_LEADERBOARD_STATS_TEST} d
                                INNER JOIN {PLAYERS_TABLE} p ON d.player_id = p.player_id
                                WHERE d.rank = %s AND d.region = %s AND d.game_mode = %s
                                ORDER BY d.day_start DESC
                                LIMIT 1;
                                """,
                                (rank, region, game_mode),
                            )
                        row = cur.fetchone()
                        if row:
                            base_message = f"{row['player_name']} is rank {row['rank']} in {row['region']} at {row['rating']}"
                            if row["rank"] <= 1000:
                                base_message += f" wallii.gg/stats/{row['player_name']}"
                            return base_message
                        else:
                            return f"No player found with rank {rank} in {region}."
                    else:
                        # No region: return top player per region
                        results = []
                        for reg in REGIONS:
                            if rank > 1000:
                                # Use current_leaderboard for ranks > 1000
                                cur.execute(
                                    f"""
                                    SELECT player_name, rating, region, rank
                                    FROM {CURRENT_LEADERBOARD}
                                    WHERE rank = %s AND region = %s AND game_mode = %s
                                    LIMIT 1;
                                    """,
                                    (rank, reg, game_mode),
                                )
                            else:
                                # Use daily_leaderboard_stats_test for ranks <= 1000
                                cur.execute(
                                    f"""
                                    SELECT p.player_name, d.rating, d.region, d.rank
                                    FROM {DAILY_LEADERBOARD_STATS_TEST} d
                                    INNER JOIN {PLAYERS_TABLE} p ON d.player_id = p.player_id
                                    WHERE d.rank = %s AND d.region = %s AND d.game_mode = %s
                                    ORDER BY d.day_start DESC
                                    LIMIT 1;
                                    """,
                                    (rank, reg, game_mode),
                                )
                            row = cur.fetchone()
                            if row:
                                results.append(
                                    f"{row['player_name']} is rank {row['rank']} in {row['region']} at {row['rating']}"
                                )
                        return (
                            " | ".join(results)
                            if results
                            else f"No players found with rank {rank}."
                        )

            # Handle name-based lookup
            table_name = (
                CURRENT_LEADERBOARD
                if (rank and rank > STATS_LIMIT)
                else LEADERBOARD_SNAPSHOTS
            )

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                rows = fetch_rank(cur, table_name)

                if not rows and table_name == LEADERBOARD_SNAPSHOTS:
                    rows = fetch_rank(cur, CURRENT_LEADERBOARD)

                if not rows:
                    return f"{query_params[0].lower()} can't be found."

                base_message = " | ".join(
                    f"{row['player_name']} is rank {row['rank']} in {row['region']} at {row['rating']}"
                    for row in rows
                )
                # Only add link if any player in the results has rank <= 1000
                if any(row["rank"] <= 1000 for row in rows):
                    base_message += f" wallii.gg/stats/{rows[0]['player_name']}"
                return base_message

        except Exception as e:
            return f"Error fetching rank: {e}"
        finally:
            self._connection_pool.putconn(conn)

    def peak(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        conn = self._get_connection()
        try:
            where_clause, query_params, _, _ = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=conn.cursor(cursor_factory=RealDictCursor),
            )

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = f"""
                    SELECT DISTINCT ON (ls.region)
                        p.player_name, ls.rating, ls.region, ls.snapshot_time
                    FROM {LEADERBOARD_SNAPSHOTS_TEST} ls
                    INNER JOIN {PLAYERS_TABLE} p ON ls.player_id = p.player_id
                    {where_clause}
                    ORDER BY ls.region, ls.rating DESC, ls.snapshot_time ASC
                """
                cur.execute(query, query_params)
                rows = cur.fetchall()

                if not rows:
                    return f"{query_params[0]} is not in the top {STATS_LIMIT}."

                return " | ".join(
                    f"{row['player_name']}'s peak rating in {row['region']} this season: {row['rating']} on {row['snapshot_time'].astimezone(TimeRangeHelper.now_la().tzinfo).strftime('%B %d, %Y %I:%M %p')} PT"
                    for row in rows
                )

        except Exception as e:
            return f"Error fetching peak: {e}"
        finally:
            self._connection_pool.putconn(conn)

    def day(
        self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0
    ) -> str:
        conn = self._get_connection()
        try:
            where_clause, query_params, _, _ = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=conn.cursor(cursor_factory=RealDictCursor),
            )

            if len(query_params) > 3:
                return "Enter a valid region with your command: like !day 1 NA"

            start_time = TimeRangeHelper.start_of_day_la(offset)
            end_time = TimeRangeHelper.start_of_day_la(offset - 1)

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First get the snapshot data
                cur.execute(
                    f"""
                    SELECT ls.rating, p.player_name, ls.snapshot_time, ls.region, ls.player_id, ls.game_mode
                    FROM {LEADERBOARD_SNAPSHOTS_TEST} ls
                    INNER JOIN {PLAYERS_TABLE} p ON ls.player_id = p.player_id
                    {where_clause}
                    AND ls.snapshot_time >= %s AND ls.snapshot_time < %s
                    ORDER BY ls.snapshot_time ASC;
                """,
                    query_params + (start_time, end_time),
                )
                snapshot_rows = cur.fetchall()

                # Now get the rank for each snapshot
                rows = []
                for snapshot_row in snapshot_rows:
                    # Get the rank for this player on the snapshot date
                    cur.execute(
                        f"""
                        SELECT rank
                        FROM {DAILY_LEADERBOARD_STATS_TEST}
                        WHERE player_id = %s AND region = %s AND game_mode = %s AND day_start = DATE(%s)
                        LIMIT 1
                        """,
                        (
                            snapshot_row["player_id"],
                            snapshot_row["region"],
                            snapshot_row["game_mode"],
                            snapshot_row["snapshot_time"],
                        ),
                    )
                    rank_result = cur.fetchone()
                    rank = rank_result["rank"] if rank_result else None

                    # Create a new row with the rank
                    row = {
                        "rank": rank,
                        "rating": snapshot_row["rating"],
                        "player_name": snapshot_row["player_name"],
                        "snapshot_time": snapshot_row["snapshot_time"],
                        "region": snapshot_row["region"],
                    }
                    rows.append(row)

            return self._summarize_progress(
                rows, offset, fallback_query=(where_clause, query_params)
            )

        except Exception as e:
            return f"Error fetching day stats: {e}"
        finally:
            self._connection_pool.putconn(conn)

    def week(
        self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0
    ) -> str:
        conn = self._get_connection()
        try:
            where_clause, query_params, _, _ = parse_rank_or_player_args(
                arg1,
                arg2,
                game_mode,
                aliases=self.aliases,
                exists_check=self.player_exists,
                db_cursor=conn.cursor(cursor_factory=RealDictCursor),
            )

            if len(query_params) > 3:
                return "Enter a valid region with your command: like !week 1 NA"

            start = TimeRangeHelper.start_of_week_la(offset)
            end = TimeRangeHelper.start_of_week_la(offset - 1)
            labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            boundaries = [start + timedelta(days=i) for i in range(8)]

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First get the snapshot data
                cur.execute(
                    f"""
                    SELECT ls.rating, p.player_name, ls.snapshot_time, ls.region, ls.player_id, ls.game_mode
                    FROM {LEADERBOARD_SNAPSHOTS_TEST} ls
                    INNER JOIN {PLAYERS_TABLE} p ON ls.player_id = p.player_id
                    {where_clause}
                    AND ls.snapshot_time >= %s AND ls.snapshot_time < %s
                    ORDER BY ls.snapshot_time ASC;
                """,
                    query_params + (start, end),
                )
                snapshot_rows = cur.fetchall()

                # Now get the rank for each snapshot
                rows = []
                for snapshot_row in snapshot_rows:
                    # Get the rank for this player on the snapshot date
                    cur.execute(
                        f"""
                        SELECT rank
                        FROM {DAILY_LEADERBOARD_STATS_TEST}
                        WHERE player_id = %s AND region = %s AND game_mode = %s AND day_start = DATE(%s)
                        LIMIT 1
                        """,
                        (
                            snapshot_row["player_id"],
                            snapshot_row["region"],
                            snapshot_row["game_mode"],
                            snapshot_row["snapshot_time"],
                        ),
                    )
                    rank_result = cur.fetchone()
                    rank = rank_result["rank"] if rank_result else None

                    # Create a new row with the rank
                    row = {
                        "rank": rank,
                        "rating": snapshot_row["rating"],
                        "player_name": snapshot_row["player_name"],
                        "snapshot_time": snapshot_row["snapshot_time"],
                        "region": snapshot_row["region"],
                    }
                    rows.append(row)

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
        finally:
            self._connection_pool.putconn(conn)

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
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # First get the snapshot data
                    cur.execute(
                        f"""
                        SELECT DISTINCT ON (ls.region)
                            ls.rating, p.player_name, ls.region, ls.player_id, ls.game_mode
                        FROM {LEADERBOARD_SNAPSHOTS_TEST} ls
                        INNER JOIN {PLAYERS_TABLE} p ON ls.player_id = p.player_id
                        {where_clause}
                        ORDER BY ls.region, ls.snapshot_time DESC;
                    """,
                        query_params,
                    )
                    snapshot_rows = cur.fetchall()

                    # Now get the rank for each snapshot
                    fallback_rows = []
                    for snapshot_row in snapshot_rows:
                        # Get the latest rank for this player
                        cur.execute(
                            f"""
                            SELECT rank
                            FROM {DAILY_LEADERBOARD_STATS_TEST}
                            WHERE player_id = %s AND region = %s AND game_mode = %s
                            ORDER BY day_start DESC
                            LIMIT 1
                            """,
                            (
                                snapshot_row["player_id"],
                                snapshot_row["region"],
                                snapshot_row["game_mode"],
                            ),
                        )
                        rank_result = cur.fetchone()
                        rank = rank_result["rank"] if rank_result else None

                        # Create a new row with the rank
                        row = {
                            "rank": rank,
                            "rating": snapshot_row["rating"],
                            "player_name": snapshot_row["player_name"],
                            "region": snapshot_row["region"],
                        }
                        fallback_rows.append(row)
            finally:
                self._connection_pool.putconn(conn)

            if not fallback_rows:
                return f"{query_params[0]} is not in the top {STATS_LIMIT}."

            # Just use the first row since we only need one result
            row = fallback_rows[0]
            suffix = (
                " last week"
                if is_week and offset > 0
                else (
                    " this week"
                    if is_week
                    else (" that day" if offset > 0 else " today")
                )
            )

            player_name = row["player_name"]
            view_link = (
                f" wallii.gg/stats/{player_name}?v={'w' if is_week else 'd'}&o={offset}"
            )

            return f"{row['player_name']} is rank {row['rank']} in {row['region']} at {row['rating']} with no games played{suffix}{view_link}"

        # Just use the first region since we only need one result
        region = next(iter(regions.keys()))
        region_rows = regions[region]

        ratings = [r["rating"] for r in region_rows]
        timestamps = [r["snapshot_time"] for r in region_rows]
        player_name = region_rows[0]["player_name"]
        rank = region_rows[-1]["rank"] or "N/A"  # Handle NULL rank
        start_rating, end_rating = ratings[0], ratings[-1]
        total_delta = end_rating - start_rating

        # Add view link
        view_link = (
            f" wallii.gg/stats/{player_name}?v={'w' if is_week else 'd'}&o={offset}"
        )

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
            rank_text = f"rank {rank}" if rank != "N/A" else "unranked"
            return f"{player_name} is {rank_text} in {region} at {end_rating} with no games played{time_suffix}{view_link}"

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
                rank_text = f"rank {rank}" if rank != "N/A" else "unranked"
                return f"{player_name} is {rank_text} in {region} at {end_rating} with no games played{suffix}{view_link}"
            else:
                suffix = " last week" if offset > 0 else ""
                return (
                    f"{player_name} {adjective} from {start_rating} to {end_rating} "
                    f"({'+' if total_delta >= 0 else ''}{total_delta}) in {region} over {delta_count} games{suffix}: {day_deltas_str} {emote}{view_link}"
                )
        else:
            deltas = [
                ratings[i + 1] - ratings[i]
                for i in range(len(ratings) - 1)
                if ratings[i + 1] != ratings[i]
            ]
            deltas_str = ", ".join([f"{'+' if d > 0 else ''}{d}" for d in deltas])
            rank_text = f"rank {rank}" if rank != "N/A" else "unranked"
            return (
                f"{player_name} {adjective} from {start_rating} to {end_rating} "
                f"({'+' if total_delta >= 0 else ''}{total_delta}) in {region} over {len(deltas)} games: {deltas_str} {emote}{view_link}"
            )

    def milestone(self, milestone_str: str, region: str = None) -> str:
        """
        Get the first player to reach a milestone rating in solo and duos.
        """
        conn = self._get_connection()
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
            base_query = f"""
                SELECT 
                    m.*,
                    TRIM(to_char(m.timestamp AT TIME ZONE 'America/Los_Angeles', 'Month')) || ' ' || 
                    TRIM(to_char(m.timestamp AT TIME ZONE 'America/Los_Angeles', 'DD HH:MI PM')) as formatted_time
                FROM {MILESTONE_TRACKING} m
                WHERE m.season = %s AND m.milestone = %s AND m.game_mode = %s
            """
            if parsed_region:
                base_query += " AND m.region = %s"
            base_query += " ORDER BY m.timestamp ASC LIMIT 1"

            # Execute queries for solo and duos
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                results = []
                for mode in ("0", "1"):
                    params = [SEASON, milestone, mode]
                    if parsed_region:
                        params.append(parsed_region)
                    cur.execute(base_query, params)
                    result = cur.fetchone()
                    if result:
                        prefix = "In Duos: " if mode == "1" else ""
                        response = (
                            f"{prefix}{result['player_name']} was the first to reach {milestone_str} "
                            f"in {result['region']} on {result['formatted_time']} PT"
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
        finally:
            self._connection_pool.putconn(conn)

    def region_stats(self, region: str = None, game_mode: str = "0") -> str:
        conn = self._get_connection()
        try:
            region = parse_server(region)
            regions = REGIONS if region is None else [region.upper()]
            results = []

            for reg in regions:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Count the number of players in the region
                    cur.execute(
                        f"""
                        SELECT COUNT(DISTINCT player_name) AS player_count
                        FROM {CURRENT_LEADERBOARD}
                        WHERE region = %s AND game_mode = %s
                    """,
                        (reg, game_mode),
                    )
                    player_count = cur.fetchone()["player_count"]

                    # Calculate the average rating of the top 25 players
                    cur.execute(
                        f"""
                        SELECT AVG(rating) AS avg_rating
                        FROM (
                            SELECT rating
                            FROM {CURRENT_LEADERBOARD}
                            WHERE region = %s AND game_mode = %s
                            ORDER BY rating DESC
                            LIMIT 25
                        ) AS top_25
                    """,
                        (reg, game_mode),
                    )
                    avg_rating = cur.fetchone()["avg_rating"]

                    if avg_rating is not None:
                        results.append(
                            f"{reg} has {player_count} players and Top 25 avg is {int(avg_rating)}"
                        )

            return " | ".join(results)

        except Exception as e:
            return f"Error fetching region stats: {e}"
        finally:
            self._connection_pool.putconn(conn)

    async def start_background_tasks(self):
        """Start background refresh tasks"""
        if self._refresh_task is None:
            self._refresh_task = asyncio.create_task(self._periodic_refresh())
            print("Started background refresh tasks")

    async def stop_background_tasks(self):
        """Stop background refresh tasks"""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            print("Stopped background refresh tasks")


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
