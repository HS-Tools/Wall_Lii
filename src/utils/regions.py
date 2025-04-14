SERVERS = ["NA", "EU", "AP"]
REGION_ALIASES = {
    "US": "NA",
    "AMERICA": "NA",
    "AMERICAS": "NA",
    "AM": "NA",
    "ASIA": "AP",
    "EUROPE": "EU",
}

def parse_server(server):
    """Convert server name to standard format"""
    if not server:
        return None
        
    server = server.upper()

    # Check if it's in the aliases
    if server in REGION_ALIASES:
        return REGION_ALIASES[server]
    
    # Check if it's already a valid server name
    if server in SERVERS:
        return server

    return None

def is_server(server):
    """Check if string is a valid server name"""
    if not server:
        return False

    server = server.upper()

    return server in REGION_ALIASES or server in SERVERS
