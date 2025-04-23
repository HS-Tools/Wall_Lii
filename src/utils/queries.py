from .regions import parse_server, is_server
from typing import Optional, List, Tuple, Union, Callable
from utils.constants import REGIONS, STATS_LIMIT


def resolve_players_from_rank(
    rank: int, region: Optional[str], game_mode: str, db_cursor
) -> List[str]:
    table_name = (
        "current_leaderboard" if rank > STATS_LIMIT else "leaderboard_snapshots"
    )
    snapshot_query = (
        "ORDER BY snapshot_time DESC" if table_name == "leaderboard_snapshots" else ""
    )
    optional_snapshot_time = (
        ", snapshot_time" if table_name == "leaderboard_snapshots" else ""
    )
    if region:
        db_cursor.execute(
            f"""
            SELECT player_name
            FROM {table_name}
            WHERE game_mode = %s AND rank = %s AND region = %s
            {snapshot_query}
            LIMIT 1;
            """,
            (game_mode, rank, region),
        )
        row = db_cursor.fetchone()
        return [row["player_name"]] if row else []
    else:
        db_cursor.execute(
            f"""
            SELECT DISTINCT ON (region) player_name
            FROM {table_name}
            WHERE game_mode = %s AND rank = %s
            ORDER BY region{optional_snapshot_time} DESC;
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
        where_clause = f"WHERE player_name IN ({placeholders}) AND game_mode = %s"
        params = tuple(player_names) + (game_mode,)
        if region:
            where_clause += " AND region = %s"
            params += (region,)
        return where_clause, params, rank, region

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

    where_clause = "WHERE player_name = %s AND game_mode = %s"
    params = (search_term, game_mode)
    if region:
        where_clause += " AND region = %s"
        params += (region,)
    return where_clause, params, rank, region
