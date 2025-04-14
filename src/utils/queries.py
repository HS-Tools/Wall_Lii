from .regions import parse_server, is_server
from typing import Optional, List, Tuple, Union, Callable

REGIONS = ["NA", "EU", "AP"]

def parse_rank_or_player_args(
    arg1: str,
    arg2: Optional[str] = None,
    game_mode: str = "0",
    aliases: Optional[dict] = None,
    exists_check: Optional[Callable] = None,
):
    region = None
    search_term = None

    a1 = arg1.strip() if arg1 else ""
    a2 = arg2.strip() if arg2 else None

    if is_server(a1.upper()):
        region = parse_server(a1.upper())
        search_term = a2
    elif a2 and is_server(a2.upper()):
        region = parse_server(a2.upper())
        search_term = a1
    else:
        search_term = a1

    is_rank = search_term and search_term.isdigit()

    # Case 1: Rank query
    if is_rank:
        where_clause = "WHERE rank = %s AND game_mode = %s"
        params = (int(search_term), game_mode)
        if region:
            where_clause += " AND region = %s"
            params += (region,)
        return where_clause, params

    # Case 2: Player name — potentially resolve alias
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

    # Construct the final query
    where_clause = "WHERE player_name = %s AND game_mode = %s"
    params = (search_term.lower(), game_mode)

    if region:
        where_clause += " AND region = %s"
        params += (region,)

    return where_clause, params