SERVERS = ["US", "EU", "AP"]
REGION_ALIASES = {
    "NA": "US",
    "AMERICA": "US",
    "AMERICAS": "US",
    "AM": "US",
    "ASIA": "AP",
    "EUROPE": "EU",
}
REGION_PRINT = {"US": "Americas", "EU": "Europe", "AP": "Asia-Pacific"}


def parseServer(server):
    """Convert server string to standard format"""
    if isinstance(server, str):
        server = server.upper()

    # Use the existing aliases
    server = REGION_ALIASES.get(server, server)
    if server in SERVERS:
        return server
    return None


def isServer(server):
    """Check if string is a valid server name"""
    if server is None:
        return False

    if isinstance(server, str):
        server = server.upper()
    return (server in SERVERS) or (server in REGION_ALIASES.keys())


def printServer(server):
    """Convert server code to display name"""
    if server in REGION_PRINT:
        return REGION_PRINT[server]
    return server
