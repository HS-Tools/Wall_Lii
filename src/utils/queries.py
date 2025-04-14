from .regions import parse_server, is_server

def parse_rank_or_player_args(arg1: str, arg2: str = None, game_mode: str = "0"):
    region = None
    search_term = None

    a1 = arg1.strip()
    a2 = arg2.strip() if arg2 else None

    if is_server(a1.upper()):
        region = parse_server(a1.upper())
        search_term = a2
    elif a2 and is_server(a2.upper()):
        region = parse_server(a2.upper())
        search_term = a1
    else:
        search_term = a1

    is_rank = search_term.isdigit()

    if is_rank:
        where_clause = "WHERE rank = %s AND game_mode = %s"
        params = (int(search_term), game_mode)
    else:
        where_clause = "WHERE player_name = %s AND game_mode = %s"
        params = (search_term.lower(), game_mode)

    if region:
        where_clause += " AND region = %s"
        params += (region,)

    return where_clause, params