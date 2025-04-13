import os
import psycopg2
from collections import defaultdict
from dotenv import load_dotenv
from utils.queries import parse_rank_or_player_args
from utils.regions import parse_server
from utils.time_range import TimeRangeHelper
from datetime import timedelta

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
                sslmode="require"
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
                f"{i+1}. {name}: {rating} ({reg})" if is_global else f"{i+1}. {name}: {rating}"
                for i, (name, rating, reg) in enumerate(results)
            )
        except Exception as e:
            return f"Error fetching leaderboard: {e}"

    def rank(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        try:
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)

            with self.conn.cursor() as cur:
                if is_rank and not arg2:
                    # No region specified — fetch for all regions
                    results = []
                    for region in REGIONS:
                        cur.execute("""
                            SELECT player_name, rating
                            FROM leaderboard_snapshots
                            WHERE rank = %s AND region = %s AND game_mode = %s
                            ORDER BY snapshot_time DESC
                            LIMIT 1;
                        """, (int(arg1), region, game_mode))
                        row = cur.fetchone()
                        if row:
                            results.append(f"{row[0]} is rank {arg1} in {region} at {row[1]}")
                    return " | ".join(results) if results else f"No players found at rank {arg1}"

                elif is_rank:
                    # Region is specified — use parsed WHERE clause
                    query = f"""
                        SELECT player_name, rating, region
                        FROM leaderboard_snapshots
                        {where_clause}
                        ORDER BY snapshot_time DESC
                        LIMIT 1;
                    """
                    cur.execute(query, query_params)
                    row = cur.fetchone()
                    if row:
                        return f"{row[0]} is rank {arg1} in {row[2]} at {row[1]}"
                    return f"No player found at rank {arg1}"

                else:
                    # Querying by player name
                    # First get the primary region data
                    query = f"""
                        SELECT rank, rating, region, player_name
                        FROM leaderboard_snapshots
                        {where_clause}
                        ORDER BY rank ASC, snapshot_time DESC
                        LIMIT 1;
                    """
                    cur.execute(query, query_params)
                    primary_row = cur.fetchone()
                    
                    if primary_row:
                        primary_rank, primary_rating, primary_region, player_name = primary_row
                        
                        # Now check if player exists on other regions
                        other_regions = []
                        for region in REGIONS:
                            if region != primary_region:
                                cur.execute("""
                                    SELECT rank, rating
                                    FROM leaderboard_snapshots
                                    WHERE player_name = %s AND region = %s AND game_mode = %s
                                    ORDER BY rank ASC, snapshot_time DESC
                                    LIMIT 1;
                                """, (player_name, region, game_mode))
                                other_row = cur.fetchone()
                                if other_row:
                                    other_rank, other_rating = other_row
                                    other_regions.append(f"rank {other_rank} {region} at {other_rating}")
                        
                        # Format the response
                        if other_regions:
                            other_regions_str = " (also " + ", ".join(other_regions) + ")"
                            return f"{player_name} is rank {primary_rank} in {primary_region} at {primary_rating}{other_regions_str}"
                        else:
                            return f"{player_name} is rank {primary_rank} in {primary_region} at {primary_rating}"
                    
                    return f"{query_params[0].lower()} can't be found."

        except Exception as e:
            return f"Error fetching rank: {e}"

    def peak(self, arg1: str, arg2: str = None, game_mode: str = "0") -> str:
        try:
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)

            with self.conn.cursor() as cur:
                if is_rank and not arg2:
                    # No region specified — fetch for all regions
                    results = []
                    for region in REGIONS:
                        cur.execute("""
                            SELECT player_name, rating, snapshot_time
                            FROM leaderboard_snapshots
                            WHERE rank = %s AND region = %s AND game_mode = %s
                            ORDER BY rating DESC
                            LIMIT 1;
                        """, (int(arg1), region, game_mode))
                        row = cur.fetchone()
                        if row:
                            date_str = row[2].strftime("%b %d, %Y") if row[2] else "unknown date"
                            results.append(f"{row[0]}'s peak rating in {region} this season: {row[1]} on {date_str}")
                    return " | ".join(results) if results else f"No players found at rank {arg1}"

                elif is_rank:
                    query = f"""
                        SELECT player_name, rating, region, snapshot_time
                        FROM leaderboard_snapshots
                        {where_clause}
                        ORDER BY rating DESC
                        LIMIT 1;
                    """
                    cur.execute(query, query_params)
                    row = cur.fetchone()
                    if row:
                        date_str = row[3].strftime("%b %d, %Y") if row[3] else "unknown date"
                        return f"{row[0]}'s peak rating in {row[2]} this season: {row[1]} on {date_str}"
                    return f"No data found for rank {arg1}"

                else:
                    query = f"""
                        SELECT player_name, rating, region, snapshot_time
                        FROM leaderboard_snapshots
                        {where_clause}
                        ORDER BY rating DESC
                        LIMIT 1;
                    """
                    cur.execute(query, query_params)
                    row = cur.fetchone()
                    if row:
                        date_str = row[3].strftime("%b %d, %Y") if row[3] else "unknown date"
                        return f"{row[0]}'s peak rating in {row[2]} this season: {row[1]} on {date_str}"
                    return f"{query_params[0]} has no recorded peak rating"

        except Exception as e:
            return f"Error fetching peak: {e}"
        
    def day(self, arg1: str, arg2: str = None, game_mode: str = "0", offset: int = 0) -> str:
        try:
            where_clause, query_params, is_rank = parse_rank_or_player_args(arg1, arg2, game_mode)
            start_time = TimeRangeHelper.start_of_day_la(offset)
            end_time = TimeRangeHelper.start_of_day_la(offset - 1)

            with self.conn.cursor() as cur:
                if is_rank and not arg2:
                    # No region specified — fetch all regions for given rank
                    results = []
                    for region in REGIONS:
                        cur.execute("""
                            SELECT player_name, rating
                            FROM leaderboard_snapshots
                            WHERE rank = %s AND region = %s AND game_mode = %s
                            AND snapshot_time >= %s AND snapshot_time < %s
                            ORDER BY snapshot_time DESC
                            LIMIT 1;
                        """, (int(arg1), region, game_mode, start_time, end_time))
                        row = cur.fetchone()
                        if row:
                            results.append(f"{row[0]} is rank {arg1} in {region} at {row[1]} (no recent games played)")
                    return " | ".join(results) if results else f"No players found at rank {arg1}"

                elif is_rank:
                    # Specific region provided
                    query = f"""
                        SELECT player_name, rating, region
                        FROM leaderboard_snapshots
                        {where_clause}
                        AND snapshot_time >= %s AND snapshot_time < %s
                        ORDER BY snapshot_time DESC
                        LIMIT 1;
                    """
                    cur.execute(query, query_params + (start_time, end_time))
                    row = cur.fetchone()
                    if row:
                        return f"{row[0]} is rank {arg1} in {row[2]} at {row[1]} (no recent games played)"
                    return f"No player found at rank {arg1}"

                # -- Player-based delta logic --
                player_name = query_params[0].lower()
                parsed_region = parse_server(arg2) if arg2 and not is_rank else None
                target_regions = [parsed_region] if parsed_region else REGIONS

                results = []

                for reg in target_regions:
                    cur.execute("""
                        SELECT rating, snapshot_time
                        FROM leaderboard_snapshots
                        WHERE player_name = %s AND region = %s AND game_mode = %s
                        AND snapshot_time >= %s AND snapshot_time < %s
                        ORDER BY snapshot_time ASC;
                    """, (player_name, reg, game_mode, start_time, end_time))
                    rows = cur.fetchall()

                    if len(rows) < 2:
                        # Not enough data to show deltas
                        cur.execute("""
                            SELECT rank, rating
                            FROM leaderboard_snapshots
                            WHERE player_name = %s AND region = %s AND game_mode = %s
                            ORDER BY snapshot_time DESC
                            LIMIT 1;
                        """, (player_name, reg, game_mode))
                        last_row = cur.fetchone()
                        if last_row:
                            rank, rating = last_row
                            results.append(f"{player_name} is rank {rank} in {reg} at {rating} with no games played")
                        continue

                    # Calculate deltas
                    ratings = [row[0] for row in rows]
                    raw_deltas = [ratings[i+1] - ratings[i] for i in range(len(ratings)-1)]
                    deltas = [d for d in raw_deltas if d != 0]

                    if not deltas:
                        cur.execute("""
                            SELECT rank, rating
                            FROM leaderboard_snapshots
                            WHERE player_name = %s AND region = %s AND game_mode = %s
                            ORDER BY snapshot_time DESC
                            LIMIT 1;
                        """, (player_name, reg, game_mode))
                        last_row = cur.fetchone()
                        if last_row:
                            rank, rating = last_row
                            results.append(f"{player_name} is rank {rank} in {reg} at {rating} with no games played")
                        continue

                    start_rating, end_rating = ratings[0], ratings[-1]
                    total_delta = end_rating - start_rating
                    deltas_str = ", ".join([f"{'+' if d > 0 else ''}{d}" for d in deltas])

                    results.append(f"{player_name} climbed from {start_rating} to {end_rating} ({'+' if total_delta >= 0 else ''}{total_delta}) in {reg} over {len(deltas)} games: {deltas_str}")

            return " | ".join(results) if results else f"{player_name} is not on any BG leaderboards."

        except Exception as e:
            return f"Error fetching day stats: {e}"
        
    def week(self, player_name: str, region: str = None, offset: int = 0, game_mode: str = "0") -> str:
        player_name = player_name.lower()
        parsed_region = parse_server(region) if region else None
        target_regions = [parsed_region] if parsed_region else REGIONS

        start_of_week = TimeRangeHelper.start_of_week_la(offset)
        day_boundaries = [start_of_week + timedelta(days=i) for i in range(8)]  # 7 days + 1 for exclusive upper bound
        weekday_labels = ["M", "T", "W", "Th", "F", "Sa", "Su"]

        try:
            results = []
            with self.conn.cursor() as cur:
                for reg in target_regions:
                    cur.execute("""
                        SELECT rating, snapshot_time
                        FROM leaderboard_snapshots
                        WHERE player_name = %s AND region = %s AND game_mode = %s
                        AND snapshot_time >= %s AND snapshot_time < %s
                        ORDER BY snapshot_time ASC;
                    """, (player_name, reg, game_mode, day_boundaries[0], day_boundaries[-1]))
                    rows = cur.fetchall()

                    if len(rows) < 2:
                        cur.execute("""
                            SELECT rank, rating
                            FROM leaderboard_snapshots
                            WHERE player_name = %s AND region = %s AND game_mode = %s
                            ORDER BY snapshot_time DESC
                            LIMIT 1;
                        """, (player_name, reg, game_mode))
                        last_row = cur.fetchone()
                        if last_row:
                            rank, rating = last_row
                            suffix = " last week" if offset > 0 else " this week"
                            results.append(f"{player_name} is rank {rank} in {reg} at {rating} with no games played{suffix}")
                        continue

                    ratings = [row[0] for row in rows]
                    timestamps = [row[1] for row in rows]
                    raw_deltas = [ratings[i+1] - ratings[i] for i in range(len(ratings)-1)]

                    delta_by_day = defaultdict(int)
                    valid_deltas = 0

                    for i in range(len(raw_deltas)):
                        delta = raw_deltas[i]
                        ts = timestamps[i+1]
                        if delta != 0:
                            for d in range(7):
                                if day_boundaries[d] <= ts < day_boundaries[d + 1]:
                                    delta_by_day[d] += delta
                                    valid_deltas += 1
                                    break

                    if not valid_deltas:
                        cur.execute("""
                            SELECT rank, rating
                            FROM leaderboard_snapshots
                            WHERE player_name = %s AND region = %s AND game_mode = %s
                            ORDER BY snapshot_time DESC
                            LIMIT 1;
                        """, (player_name, reg, game_mode))
                        last_row = cur.fetchone()
                        if last_row:
                            rank, rating = last_row
                            suffix = " last week" if offset > 0 else " this week"
                            results.append(f"{player_name} is rank {rank} in {reg} at {rating} with no games played{suffix}")
                        continue

                    start_rating, end_rating = ratings[0], ratings[-1]
                    total_delta = end_rating - start_rating
                    suffix = " last week" if offset > 0 else ""

                    day_deltas_str = ", ".join(
                        f"{weekday_labels[i]}: {'+' if delta_by_day[i] > 0 else ''}{delta_by_day[i]}"
                        for i in range(7)
                    )

                    results.append(
                        f"{player_name} climbed from {start_rating} to {end_rating} ({'+' if total_delta >= 0 else ''}{total_delta}) in {reg} over {valid_deltas} games{suffix}: {day_deltas_str}"
                    )

            return " | ".join(results) if results else f"{player_name} is not on any BG leaderboards."

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
    print("Day tests ---------------")
    print(db.day("jeef", "NA", offset=0))  # today's progress
    print(db.day("jeef", "NA", offset=1))  # yesterday's progress
    print(db.day("jeef", offset=0))
    print(db.day("jeef", "afsdfasf"))
    print(db.day("adsfaeafeawfew"))
    print(db.day("lii"))
    print(db.day("1", "na"))
    print("Week tests ---------------")
    print(db.week("jeef", "NA", offset=0))  # today's progress
    print(db.week("jeef", "NA", offset=1))  # yesterday's progress
    print(db.week("jeef", offset=0))
    print(db.week("jeef", "afsdfasf"))
    print(db.week("adsfaeafeawfew"))
    print(db.week("lii"))
    print(db.week("lii", offset=1))

    db.close()