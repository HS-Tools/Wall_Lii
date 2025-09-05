from .regions import parse_server, is_server
from typing import Optional, List, Tuple, Union, Callable
from utils.constants import REGIONS, STATS_LIMIT
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import NORMALIZED_TABLES

# New normalized table names
DAILY_LEADERBOARD_STATS = NORMALIZED_TABLES["daily_leaderboard_stats"]
LEADERBOARD_SNAPSHOTS = NORMALIZED_TABLES["leaderboard_snapshots"]
CURRENT_LEADERBOARD = "current_leaderboard"  # Keep old name for now
PLAYERS_TABLE = NORMALIZED_TABLES["players"]


def resolve_players_from_rank(
    rank: int, region: Optional[str], game_mode: str, db_cursor
) -> List[str]:
    if rank > STATS_LIMIT:
        # Use current_leaderboard for ranks > 1000
        table_name = CURRENT_LEADERBOARD
        table_alias = "cl"

        if region:
            db_cursor.execute(
                f"""
                SELECT player_name
                FROM {table_name} {table_alias}
                WHERE {table_alias}.game_mode = %s AND {table_alias}.rank = %s AND {table_alias}.region = %s
                LIMIT 1;
                """,
                (game_mode, rank, region),
            )
            row = db_cursor.fetchone()
            return [row["player_name"]] if row else []
        else:
            db_cursor.execute(
                f"""
                SELECT DISTINCT ON ({table_alias}.region) player_name
                FROM {table_name} {table_alias}
                WHERE {table_alias}.game_mode = %s AND {table_alias}.rank = %s
                ORDER BY {table_alias}.region DESC;
                """,
                (game_mode, rank),
            )
            return [r["player_name"] for r in db_cursor.fetchall()]
    else:
        # Use daily_leaderboard_stats for ranks <= 1000
        if region:
            db_cursor.execute(
                f"""
                SELECT p.player_name
                FROM {DAILY_LEADERBOARD_STATS} d
                INNER JOIN {PLAYERS_TABLE} p ON d.player_id = p.player_id
                WHERE d.game_mode = %s AND d.rank = %s AND d.region = %s
                ORDER BY d.day_start DESC
                LIMIT 1;
                """,
                (game_mode, rank, region),
            )
            row = db_cursor.fetchone()
            return [row["player_name"]] if row else []
        else:
            db_cursor.execute(
                f"""
                SELECT DISTINCT ON (d.region) p.player_name
                FROM {DAILY_LEADERBOARD_STATS} d
                INNER JOIN {PLAYERS_TABLE} p ON d.player_id = p.player_id
                WHERE d.game_mode = %s AND d.rank = %s
                ORDER BY d.region, d.day_start DESC;
                """,
                (game_mode, rank),
            )
            return [r["player_name"] for r in db_cursor.fetchall()]


def parse_rank_or_player_args(
    arg1: str,
    arg2: Optional[str] = None,
    game_mode: str = "0",
    aliases: Optional[dict] = None,
    exists_check: Optional[Callable] = None,
    db_cursor=None,
):
    region = None
    search_term = None

    a1 = arg1.lower().strip() if arg1 else ""
    a2 = arg2.lower().strip() if arg2 else None

    if is_server(a1.upper()):
        region = parse_server(a1.upper())
        search_term = a2
    elif a2 and is_server(a2.upper()):
        region = parse_server(a2.upper())
        search_term = a1
    else:
        search_term = a1

    is_rank = search_term and search_term.isdigit()
    rank = int(search_term) if is_rank else None

    if is_rank:
        if db_cursor is None:
            raise ValueError("db_cursor required to resolve rank")
        player_names = resolve_players_from_rank(
            int(search_term), region, game_mode, db_cursor
        )
        if not player_names:
            raise ValueError(f"No players found at rank {search_term}")

        placeholders = ", ".join(["%s"] * len(player_names))
        where_clause = f"WHERE p.player_name IN ({placeholders}) AND ls.game_mode = %s"
        params = tuple(player_names) + (game_mode,)
        if region:
            where_clause += " AND ls.region = %s"
            params += (region,)
        return where_clause, params, rank, region

    print(search_term)

    if aliases and search_term and not is_rank:
        raw_term = search_term.lower()

        # Check if this is an alias
        if raw_term in aliases:
            # If we have an exists_check function, verify if the original name exists
            if exists_check and region:
                if not exists_check(raw_term, region, game_mode):
                    search_term = aliases[raw_term]
            elif exists_check and not region:
                # Check all regions - if player doesn't exist in any, use the alias
                exists_in_any = False
                for reg in REGIONS:
                    if exists_check(raw_term, reg, game_mode):
                        exists_in_any = True
                        break
                if not exists_in_any:
                    search_term = aliases[raw_term]
            else:
                # No exists_check, just use the alias
                search_term = aliases[raw_term]

    where_clause = "WHERE p.player_name = %s AND ls.game_mode = %s"
    params = (search_term, game_mode)
    if region:
        where_clause += " AND ls.region = %s"
        params += (region,)
    return where_clause, params, rank, region
