REGIONS = ['US', 'EU', 'AP']
REGION_ALIASES = {
    'NA':'US',
    'AMERICA':'US',
    'AMERICAS':'US',
    'ASIA':'AP',
    'EUROPE':'EU'
}
REGION_PRINT = {
    'US': 'Americas',
    'EU': 'Europe',
    'AP': 'Asia-Pacific'
}


def parseRegion(region):
    if type(region) == str:
        region = region.upper()

    region = REGION_ALIASES.get(region, region)
    if region in REGIONS:
        return region
    return None

def isRegion(region):
    if region == None:
        return True

    if type(region) == str:
        region = region.upper()
    return (region in REGIONS) or (region in REGION_ALIASES.keys())

def printRegion(region):
    if region in REGION_PRINT:
        return REGION_PRINT[region]
    return region
