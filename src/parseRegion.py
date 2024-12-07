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
    """Convert server name to standard format"""
    server = server.upper()

    # Map US to NA
    if server in ["US", "NA", "AMERICA", "AMERICAS"]:
        return "NA"
    elif server in ["EU", "EUROPE"]:
        return "EU"
    elif server in ["AP", "ASIA"]:
        return "AP"

    return None


def isServer(server):
    """Check if string is a valid server name"""
    if not server:
        return False

    server = server.upper()
    valid_servers = {
        "NA",
        "US",
        "AMERICA",
        "AMERICAS",  # North America
        "EU",
        "EUROPE",  # Europe
        "AP",
        "ASIA",  # Asia Pacific
    }

    return server in valid_servers


def printServer(server):
    """Convert server code to display name"""
    if server in REGION_PRINT:
        return REGION_PRINT[server]
    return server
