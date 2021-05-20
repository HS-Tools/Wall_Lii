REGIONS = ['US', 'EU', 'AP']
REGION_ALIASES = {
    'NA':'US',
    'AMERICA':'US',
    'AMERICAS':'US',
    'ASIA':'AP',
    'EUROPE':'EU'
}

def parseRegion(region):
    if type(region) == str:
        region = region.upper()

    region = REGION_ALIASES.get(region, region)
    if region in REGIONS:
        return region

def isRegion(region):
    print(region)
    if region == None:
        return True

    if type(region) == str:
        region = region.upper()
    return (region in REGIONS) or (region in REGION_ALIASES.keys())
