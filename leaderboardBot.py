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

        tag = self.getFormattedTag(tag)
        items = self.getPlayerData(tag, region)

        text = f"{tag} is not on {region if region else 'any BG'} leaderboards liiCat"
        highestRank = 9999

        for item in items:
            if item['Rank'] < highestRank:
                highestRank = item['Rank']
                rank = item['Rank']
                region = item['Region']
                rating = item['Ratings'][-1]
                
                text = "{} is rank {} in {} with {} mmr liiHappyCat" \
                    .format(tag, rank, region, rating)
        
        # if tag == 'nina' or tag == 'ninaisnoob':
        #     return '{} is rank 69 in Antartica with 16969 mmr ninaisFEESH'.format(tag)

        # if tag == 'gomez':
        #     return '{} is a cat, cats do not play BG'.format(tag)

        return text

    def getFormattedTag(self, tag):
        tag = tag.lower()
        
        if tag in alias:
            tag = alias[tag]

        return tag

lb = LeaderBoardBot()
print(lb.getRankText('waterloo', 'EU'))


    # def getDailyStatsText(self, tag):
    #     longestRecordLength = 1

    #     encodedTag = self.getEncodedTag(tag)
        
    #     if encodedTag not in self.dailyStats:
    #         return "{} is not on any BG leaderboards liiCat".format(encodedTag.decode())

    #     text = "{} and has not played any games today liiCat".format(self.getRankText(tag))

    #     for region in REGIONS:
    #         if region in self.dailyStats[encodedTag]:
    #             ratings = self.dailyStats[encodedTag][region]

    #             if len(ratings) > longestRecordLength:
    #                 longestRecordLength = len(ratings)
    #                 text = f"{encodedTag.decode()} started today at {ratings[0]} in {region} and is now {self.currentLeaderboard[region][encodedTag]['rating']} with {len(ratings)-1} games played. Their record is: {self.getDeltas(ratings)}"

    #     return text

    # # This should only get called if ratings has more than 1 entry
    # def getDeltas(self, ratings):
    #     lastRating = ratings[0]
    #     deltas = []
        
    #     for rating in ratings[1:]:
    #         deltas.append('{0:+d}'.format(rating - lastRating))

    #         lastRating = rating

    #     return ', '.join(deltas)
    

            

    # def getRankText(self, tag, region = ""):
        
    #     if tag == 'nina' or tag == 'ninaisnoob':
    #         return '{} is rank 69 in Antartica with 16969 mmr ninaisFEESH'.format(tag)

    #     if tag == 'gomez':
    #         return '{} is a cat, cats do not play BG'.format(tag)

    #     # Resolve alias if aliased, returns None if region is invalid.
    #     region = parseRegion(region)
        
    #     if region is not None:
    #         specified_region = True
    #         regions = [region]
    #     else:
    #         specified_region = False
    #         regions = REGIONS

    #     highestRank = 9999

    #     encodedTag = self.getEncodedTag(tag)
    #     text = f"{encodedTag.decode()} is not on {region if specified_region else 'any BG'} leaderboards liiCat"
    #     for region in regions:
    #         if encodedTag in self.currentLeaderboard[region]:
    #             rank = self.currentLeaderboard[region][encodedTag]['rank']
    #             rating = self.currentLeaderboard[region][encodedTag]['rating']

    #             if int(rank) < highestRank:
    #                 highestRank = int(rank)
    #                 text = "{} is rank {} in {} with {} mmr liiHappyCat" \
    #                 .format(encodedTag.decode(), rank, region, rating)

    #     return text

    # def deleteDup(self, lst):
    #     if len(lst) > 2:
    #         if lst[-1] == lst[-3]:
    #             lst = lst[-2:]

    #             return lst
    #     return lst


