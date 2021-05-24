import boto3
from boto3.dynamodb.conditions import Key, Attr
from parseRegion import REGIONS, parseRegion, isRegion
import threading
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

alias = {
    'waterloo': 'waterloooooo',
    'jeef': 'jeffispro',
    'jeff': 'jeffispro',
    'victor': 'twlevewinshs',
    'sleepy': 'foreversleep',
    'dogdog': 'dog',
    'pockyplays': 'pocky',
    'nina': 'ninaisnoob',
    'liihs': 'lii',
    'purple_hs': 'purple',
    'deathitselfhs': 'deathitself',
    'tylerootd': 'tyler',
    'mrincrediblehs': 'mrincredible',
    'sevel07': 'sevel',
    'jubjoe': 'felix',
    'quinnabr': 'middnie'
}
eggs = { # Easter eggs
    'salami': 'salami is rank 69 in Antartica with 16969 mmr ninaisFEESH',
    'gomez': 'gomez is a cat, cats do not play BG',
    '420': "don't do drugs kids",
    '16969': 'salami is rank 69 in Antartica with 16969 mmr ninaisFEESH'
}

class LeaderBoardBot:
    db = None
    table = None
    yesterday_table = None

    def __init__(self, **kargs):
        self.db = boto3.resource('dynamodb', **kargs)
        self.table = self.db.Table(os.environ['TABLE_NAME'])
        self.yesterday_table = self.db.Table('yesterday-rating-record-table')

    def parseArgs(self, default, *args):
        if (len(args) == 0):
            return [default, None]
        elif (len(args) == 1):
            if isRegion(args[0]):
                return [default, parseRegion(args[0])]
            else:
                return [args[0], None]
        else:
            if not isRegion(args[1]):
                return [args[0], None]
            else:
                return [args[0], parseRegion(args[1])]

    def getPlayerData(self, tag, table, region=None):
        items = []
        if region != None:
            response = table.get_item(Key={
                'PlayerName':tag,
                'Region':region
            })

            if 'Item' in response:
                items.append(response['Item'])
        else:
            for region in REGIONS:
                response = table.get_item(Key={
                    'PlayerName':tag,
                    'Region': region
                })

                if 'Item' in response:
                    items.append(response['Item'])

        return items
        # Looks like:
        # [{'Rank': Decimal('12'), 'TTL': Decimal('1616569200'), 'PlayerName': 'lii', 'Region': 'US', 'Ratings': [Decimal('14825')]}]

    def getEntryFromRank(self, rank, region, yesterday=False):
        table = self.yesterday_table if yesterday else self.table
        response = table.scan(
            Select = 'ALL_ATTRIBUTES',
            FilterExpression=Attr('Rank').eq(rank),
        )

        if 'Items' in response:
            response = response['Items']
        else:
            response = None

        response = [it for it in response if it['Region'] == region]

        return response

    def getRankText(self, tag, region=None, yesterday=False):
        if tag in eggs.keys():
            return eggs[tag]

        region = parseRegion(region)
        tag = self.getFormattedTag(tag)

        if tag.isdigit(): ## jump to search by number
            tag = int(tag)
            if tag > 200 or tag < 1:
                return f"invalid number rank {tag}, I only track the top 200 players liiWait"

            items = self.getEntryFromRank(tag, region, yesterday)

            if len(items) > 0:
                tag = items[0]['PlayerName']
            else:
                return "Invalid or no region given for rank lookup"
        else:
            items = self.getPlayerData(tag, self.yesterday_table if yesterday else self.table, region)

        text = f"{tag} is not on {region if region else 'any BG'} leaderboards liiCat"
        highestRank = 9999

        for item in items:
            if item['Rank'] < highestRank:
                highestRank = item['Rank']
                rank = item['Rank']
                region = item['Region']

                if (len(item['Ratings']) <= 0):
                    break

                rating = item['Ratings'][-1]
                time = item['LastUpdate']

                if not yesterday and self.checkIfTimeIs30MinutesInThePast(time):
                    text = f'{tag} dropped from the {region} leaderboards but was {rating} mmr earlier today liiCat'
                else:
                    text = f'{tag} {"is" if not yesterday else "was"} rank {rank} in {region} with {rating} mmr liiHappyCat'

        return text

    def getFormattedTag(self, tag):
        tag = tag.lower()

        if tag in alias:
            tag = alias[tag]

        return tag

    def getDailyStatsText(self, tag, region=None, yesterday=False):
        if tag in eggs.keys():
            return eggs[tag]

        region = parseRegion(region)
        tag = self.getFormattedTag(tag)

        if tag.isdigit(): ## jump to search by number
            tag = int(tag)
            if tag > 200 or tag < 1:
                return f"invalid number rank {tag}, I only track the top 200 players liiWait"
            items = self.getEntryFromRank(tag, region, yesterday)
            
            if len(items) > 0:
                tag = items[0]['PlayerName']
            else:
                return "Invalid or no region given for rank lookup"
        else:
            items = self.getPlayerData(tag, self.yesterday_table if yesterday else self.table, region)

        longestRecord = 1

        if len(items) == 0:
            return f"{tag} is not on {region if region else 'any BG'} leaderboards liiCat"

        text = f'{self.getRankText(tag, region, yesterday=yesterday)} and {"has not played any games today liiCat" if not yesterday else "did not play any games yesterday liiCat"}'

        for item in items:
            if len(item['Ratings']) > longestRecord:
                longestRecord = len(item['Ratings'])
                ratings = item['Ratings']
                self.removeDuplicateGames(ratings)
                region = item['Region']

                emote = 'liiHappyCat' if ratings[-1] > ratings[0] else 'liiCat'

                text = f"{tag} started {'today' if not yesterday else 'yesterday'} at {ratings[0]} in {region} and {'is now' if not yesterday else 'ended at' } \
                {ratings[-1]} with {len(ratings)-1} games played. {emote} Their record {'is' if not yesterday else 'was'}: {self.getDeltas(ratings)}"

        return text

    def getMostMMRChanged(self, num, highest):
        # For each entry in the leaderboard, get the tag, region and mmr change
        # At the end sort the entries by mmr change and return the top 5 people

        response = self.table.scan()
        items = response['Items']

        climbers = []

        for item in items:
            obj = {
                'Tag': item['PlayerName'],
                'Region': item['Region'],
                'Start': item['Ratings'][0],
                'End': item['Ratings'][-1],
                'Change': int(item['Ratings'][-1] - item['Ratings'][0])
            }

            climbers.append(obj)

        climbers.sort(key=lambda x: x['Change'], reverse=highest)

        try:
            return climbers[0:num]
        except:
            return []

    def getHardcoreGamers(self, num):
        response = self.table.scan()
        items = response['Items']

        gamers = []

        for item in items:
            games = item['Ratings']
            self.removeDuplicateGames(games)
            gameCount = len(games)

            obj = {
                'Tag': item['PlayerName'],
                'Region': item['Region'],
                'Gamecount': gameCount
            }

            gamers.append(obj)

        gamers.sort(key=lambda x: x['Gamecount'], reverse=True)

        try:
            return gamers[0:num]
        except:
            return []

    def getHighestRatingAndActivePlayers(self, num):
        response = self.table.scan()
        items = response['Items']

        highest = []

        for item in items:
            ratings = item['Ratings']
            self.removeDuplicateGames(ratings)

            obj = {
                'Tag': item['PlayerName'],
                'Region': item['Region'],
                'Start': item['Ratings'][0],
                'End': item['Ratings'][-1],
                'Gamecount': len(ratings),
                'Change': int(item['Ratings'][-1] - item['Ratings'][0])
            }

            if len(ratings) > 1:
                highest.append(obj)

        highest.sort(key=lambda x: x['End'], reverse=True)

        try:
            return highest[0:num]
        except:
            return []

    # This should only get called if ratings has more than 1 entry
    def getDeltas(self, ratings):
        lastRating = ratings[0]
        deltas = []

        for rating in ratings[1:]:
            deltas.append('{0:+d}'.format(int(rating - lastRating)))

            lastRating = rating

        return ', '.join(deltas)

    def checkIfTimeIs30MinutesInThePast(self, time):
        currentTime = datetime.utcnow()
        try:
            time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
        except:
            return False

        delta = (currentTime - time)
        minuteDifference = delta.total_seconds() / 60

        return minuteDifference > 30

    # We want to remove any patterns like: +x, -x, +x and replace it with +x
    # This corresponds to a rating pattern like: x, y, x, y and I need to make it look like: x, y
    def removeDuplicateGames(self, ratings):
        indicesToRemove = set()
        if len(ratings) >= 3:
            for i in range(0, len(ratings) - 2):
                if ratings[i] == ratings[i+2]:
                    indicesToRemove.add(i+1)

        indicesToRemove = list(indicesToRemove)
        indicesToRemove.sort()
        indicesToRemove.reverse()

        for index in indicesToRemove:
            del ratings[index]

    def clearDailyTable(self):
        today_scan = self.table.scan()

        # Delete the entire today table
        with self.table.batch_writer() as batch:
            for each in today_scan['Items']:
                batch.delete_item(
                    Key = {
                        'PlayerName': each['PlayerName'],
                        'Region': each['Region']
                    }
                )

