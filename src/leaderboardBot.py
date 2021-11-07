from re import I
import boto3
from boto3.dynamodb.conditions import Key, Attr
import dotenv
from parseRegion import REGIONS, parseRegion, isRegion, printRegion
import threading
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from default_alias import alias as default_alias
from default_channels import channels as default_channels

eggs = { # Easter eggs
    'salami': 'salami is rank 69 in Antartica with 16969 mmr ninaisFEESH',
    'gomez': 'gomez is a cat, cats do not play BG',
    '420': "don't do drugs kids",
    '16969': 'salami is rank 69 in Antartica with 16969 mmr ninaisFEESH'
}

help_msg = "@liiHS I had an issue, send help liiWait"

class LeaderBoardBot:
    resource = None
    table = None
    yesterday_table = None
    alias = {}

    def __init__(self, table_name=None, **kwargs):
        if table_name is None:
            table_name = os.environ['TABLE_NAME']
        self.resource = boto3.resource('dynamodb', **kwargs)
        self.table = self.resource.Table(table_name)
        self.yesterday_table = self.resource.Table('yesterday-rating-record-table')
        self.alias_table = self.resource.Table('player-alias-table')
        self.channel_table = self.resource.Table('channel-table')
        self.updateAlias()

    def parseArgs(self, default, *args):
        args = list(args)
        for i, arg in enumerate(args):
            if '@' == arg[0]:
                args[i] = arg[1:] ## take the end of the string
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

    def getFormattedTag(self, tag):
        tag = tag.lower()
        return tag


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
            FilterExpression=Attr('Rank').eq(rank),
        )
        print(response)
        return [it for it in response['Items'] if it['Region'] == region]


    def findPlayer(self, tag, region, yesterday):
        ## format the data
        region = parseRegion(region)
        tag = self.getFormattedTag(tag)
        table = self.yesterday_table if yesterday else self.table

        ## check if tag on leaderboard
        player_data = self.getPlayerData(tag, table, region)
        if len(player_data) > 0:
            return tag, region, player_data, ""

        ## check if alias is on leaderboard
        if tag in self.alias:
            alias = self.alias[tag]
            alias = self.getFormattedTag(alias)
            player_data = self.getPlayerData(alias, table, region)
        if len(player_data) > 0:
            tag = alias
            return tag, region, player_data, ""

        ## check if easter egg before digit because of numerical eggs
        if tag in eggs:
            return tag, region, [], eggs[tag]

        ## check if is digit
        if tag.isdigit(): ## jump to search by number
            num = int(tag)
            if num <= 200 and num >= 1 and region is not None:
                player_data = self.getEntryFromRank(num, region, yesterday)
                return tag, region, player_data, ""
            else:
                msg =  f"invalid number rank {tag} liiWait"
                if num > 200 or num < 1:
                    msg += ", I only track the top 200 players"
                if region is None:
                    msg += ", region must be provided"
                return tag, region, [], msg

        ## return nothing
        return tag, region, [], f'{tag} {"is" if not yesterday else "was"} not on {printRegion(region) if region else "any BG"} leaderboards liiCat'


    def formatRankText(self, yesterday, player_data):
        highestRank = 9999
        for item in player_data:
            if item['Rank'] < highestRank:
                tag = item['PlayerName']
                highestRank = item['Rank']
                rank = item['Rank']
                region = printRegion(item['Region'])

                if (len(item['Ratings']) <= 0):
                    break

                rating = item['Ratings'][-1]

                if item['Rank'] < 0:
                    text = f'{tag} dropped from the {region} leaderboards but was {rating} mmr earlier {"today" if not yesterday else "Yesterday"} liiCat'
                else:
                    text = f'{tag} {"is" if not yesterday else "was"} rank {rank} in {region} with {rating} mmr liiHappyCat'
        return text

    def getRankText(self, tag, region=None, yesterday=False):
        tag, region, player_data, msg = self.findPlayer(tag, region, yesterday)
        if len(player_data) > 0:
            return self.formatRankText(yesterday, player_data)
        elif len(msg) > 0:
            return msg
        else:
            return help_msg


    def formatDailyStatsText(self, yesterday, player_data):
        text = f'{self.formatRankText(yesterday, player_data)} and {"has not played any games today liiCat" if not yesterday else "did not play any games yesterday liiCat"}'
        longestRecord = 1

        for item in items:
            if len(item['Ratings']) > longestRecord:
                tag = item['PlayerName']
                longestRecord = len(item['Ratings'])
                ratings = item['Ratings']
                region = printRegion(item['Region'])

                emote = 'liiHappyCat' if ratings[-1] > ratings[0] else 'liiCat'

                text = f"{tag} started {'today' if not yesterday else 'yesterday'} at {ratings[0]} in {region} and {'is now' if not yesterday else 'ended at' } \
                {ratings[-1]} with {len(ratings)-1} games played. {emote} Their record {'is' if not yesterday else 'was'}: {self.getDeltas(ratings)}"

        return text


    def getDailyStatsText(self, tag, region=None, yesterday=False):
        tag, region, player_data, msg = self.findPlayer(tag, region, yesterday)
        if len(player_data) > 0:
            return self.formatDailyStatsText(yesterday, player_data)
        elif len(msg) > 0:
            return msg
        else:
            return help_text

    def getLeaderboardThreshold(self, rank=200):
        table = self.table
        response = table.scan(
            FilterExpression=Attr('Rank').eq(rank),
        )

        dict = {}

        for item in response['Items']:
            region = item['Region']
            rating = item['Ratings'][-1]
            dict[region] = rating

        return dict

    def getMostMMRChanged(self, num, highest):
        # For each entry in the leaderboard, get the tag, region and mmr change
        # At the end sort the entries by mmr change and return the top 5 people

        response = self.table.scan()
        items = response['Items']

        climbers = []

        for item in items:
            if len(item['Ratings']) > 0:
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
            ratings = item['Ratings']
            gameCount = len(ratings) - 1

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
            if len(item['Ratings']) > 0:
                ratings = item['Ratings']

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

    def updateAlias(self):
        response = self.alias_table.scan()
        self.alias = {it['Alias']:it['PlayerName'] for it in response['Items']}

    def getChannels(self):
        response = self.channel_table.scan()
        return {it['ChannelName']:it['PlayerName'] for it in response['Items']}

    def addChannel(self, channel, playerName, new=True):
        item = {
            'ChannelName': channel,
            'PlayerName': playerName,
        }
        if new:
            item['New'] = new

        self.addAlias(channel, playerName)
        
        self.channel_table.put_item(Item=item)

    def addAlias(self, alias, playerName, new=True):
        item = {
            'Alias': alias,
            'PlayerName': playerName,
        }

        self.alias[alias] = playerName

        if new:
            item['New'] = new
        self.alias_table.put_item(Item=item)

    def deleteAlias(self, alias):
        key = {
            'Alias': alias,
        }
        response = self.alias_table.get_item(Key=key)
        if 'Item' in response:
            self.alias_table.delete_item(Key=key)
        if alias in self.alias:
            del self.alias[alias]


    def deleteChannel(self, channel):
        key = {
            'ChannelName': channel,
        }
        self.channel_table.delete_item(Key=key)

    def getNewChannels(self):
        response = self.channel_table.scan(
            FilterExpression=Attr('New').eq(True),
        )
        with self.channel_table.batch_writer() as batch:
            for item in response['Items']:
                item.pop('New', None)
                batch.put_item(item)
        return {it['ChannelName']:it['PlayerName'] for it in response['Items']}

    def getNewAlias(self):
        response = self.alias_table.scan(
            FilterExpression=Attr('New').eq(True),
        )
        with self.alias_table.batch_writer() as batch:
            for item in response['Items']:
                item.pop('New', None)
                batch.put_item(item)

                self.alias[item['Alias']] = item['PlayerName']
        return self.alias

    def addDefaultAlias(self):
        for key in default_alias:
            self.addAlias(key, default_alias[key], False)

    def addChannels(self):
        for key in default_channels:
            self.addChannel(key, default_channels[key], False)
