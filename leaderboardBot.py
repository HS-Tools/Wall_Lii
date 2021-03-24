import boto3
from parseRegion import REGIONS, parseRegion
import threading
import requests
import os

alias = {
    'waterloo': 'waterloooooo',
    'jeef': 'jeffispro',
    'jeff': 'jeffispro',
    'victor': 'diyingli',
    'sleepy': 'foreversleep'
}

class LeaderBoardBot:
    db = None
    table = None

    def __init__(self):
        self.db = boto3.resource('dynamodb', aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['AWS_ACCESS_KEY'], region_name=os.environ['REGION'])
        self.table = self.db.Table(os.environ['TABLE_NAME'])

    def getPlayerData(self, tag, region=None):

        items = []

        if region != None:
            response = self.table.get_item(Key={
                'PlayerName':tag,
                'Region':region
            })

            if 'Item' in response:
                items.append(response['Item'])
        else:
            for region in REGIONS:
                response = self.table.get_item(Key={
                    'PlayerName':tag,
                    'Region': region
                })
                
                if 'Item' in response:
                    items.append(response['Item'])

        return items
        # Looks like: 
        # [{'Rank': Decimal('12'), 'TTL': Decimal('1616569200'), 'PlayerName': 'lii', 'Region': 'US', 'Ratings': [Decimal('14825')]}]


    def getRankText(self, tag, region=None):

        region = parseRegion(region)
        tag = self.getFormattedTag(tag)
        items = self.getPlayerData(tag, region)

        text = f"{tag} is not on {region if region else 'any BG'} leaderboards liiCat"
        highestRank = 9999

        # Easter eggs
        if tag == 'nina' or tag == 'ninaisnoob':
            text = '{} is rank 69 in Antartica with 16969 mmr ninaisFEESH'.format(tag)

        if tag == 'gomez':
            text = '{} is a cat, cats do not play BG'.format(tag)

        for item in items:
            if item['Rank'] < highestRank:
                highestRank = item['Rank']
                rank = item['Rank']
                region = item['Region']
                rating = item['Ratings'][-1]
                
                text = "{} is rank {} in {} with {} mmr liiHappyCat" \
                    .format(tag, rank, region, rating)

        return text

    def getFormattedTag(self, tag):
        tag = tag.lower()
        
        if tag in alias:
            tag = alias[tag]

        return tag

    def getDailyStatsText(self, tag, region=None):

        region = parseRegion(region)
        tag = self.getFormattedTag(tag)
        items = self.getPlayerData(tag, region)
        longestRecord = 1

        if len(items) == 0:
            return f"{tag} is not on {region if region else 'any BG'} leaderboards liiCat"

        text = "{} and has not played any games today liiCat".format(self.getRankText(tag, region))

        for item in items:
            if len(item['Ratings']) > longestRecord:
                longestRecord = len(item['Ratings'])
                ratings = item['Ratings']
                region = item['Region']

                text = f"{tag} started today at {ratings[0]} in {region} and is now {ratings[-1]} with {len(ratings)-1} games played. Their record is: {self.getDeltas(ratings)}"

        return text

    # This should only get called if ratings has more than 1 entry
    def getDeltas(self, ratings):
        lastRating = ratings[0]
        deltas = []
        
        for rating in ratings[1:]:
            deltas.append('{0:+d}'.format(int(rating - lastRating)))

            lastRating = rating

        return ', '.join(deltas)

