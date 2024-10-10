import os
from datetime import datetime
from operator import indexOf
from re import I

import aiocron
import boto3
import dotenv
import requests
from boto3.dynamodb.conditions import Attr, Key
from dotenv import load_dotenv

from default_alias import alias as default_alias
from default_channels import channels as default_channels
from parseRegion import REGIONS, isRegion, parseRegion, printRegion

eggs = {  # Easter eggs
    "salami": "salami is rank 69 in Antarctica with 16969 mmr CORM",
    "gomez": "gomez is a cat, cats do not play BG",
    "16969": "salami is rank 69 in Antarctica with 16969 mmr CORM",
}

help_msg = "@liiHS I had an issue, send help liiWait"


class LeaderBoardBot:
    resource = None
    table = None
    yesterday_table = None
    alias = {}

    def __init__(self, table_name=None, **kwargs):
        if table_name is None:
            table_name = os.environ["TABLE_NAME"]
        self.resource = boto3.resource("dynamodb", **kwargs)
        self.table = self.resource.Table(table_name)
        self.yesterday_table = self.resource.Table("yesterday-rating-record-table")
        self.alias_table = self.resource.Table("player-alias-table")
        self.channel_table = self.resource.Table("channel-table")
        self.patch_link = "Waiting to fetch latest post from https://hearthstone.blizzard.com/en-us/news"
        self.updateAlias()
        aiocron.crontab("* * * * *", func=self.fetchPatchLink)

    def parseArgs(self, default, *args):
        args = list(args)
        for i, arg in enumerate(args):
            if len(arg) > 0 and ("/" == arg[0] or "!" == arg[0]):
                return ["Please don't try to hack me", None]
        # Check for that special character which sometimes shows up during repeated 0 arg calls
        if len(args) == 0 or args[0] == "\U000e0000":
            return [default, None]
        elif len(args) == 1:
            if isRegion(args[0]):
                return [default, parseRegion(args[0])]
            else:
                return [args[0], None]
        else:
            if isRegion(args[1]):
                return [args[0], parseRegion(args[1])]
            elif isRegion(args[0]):
                # swap region and arguement order
                return [args[1], parseRegion(args[0])]
            else:
                return [args[0], None]

    def getFormattedTag(self, tag):
        tag = tag.lower()
        return tag

    def getPlayerData(self, tag, table, region=None):
        items = []
        if region != None:
            response = table.get_item(Key={"PlayerName": tag, "Region": region})

            if "Item" in response:
                items.append(response["Item"])
        else:
            for region in REGIONS:
                response = table.get_item(Key={"PlayerName": tag, "Region": region})

                if "Item" in response:
                    items.append(response["Item"])

        return items
        # Looks like:
        # [{'Rank': Decimal('12'), 'TTL': Decimal('1616569200'), 'PlayerName': 'lii', 'Region': 'US', 'Ratings': [Decimal('14825')]}]

    def getEntryFromRank(self, rank, region, yesterday=False):
        table = self.yesterday_table if yesterday else self.table
        response = table.scan(
            FilterExpression=Attr("Rank").eq(rank),
        )
        return [it for it in response["Items"] if it["Region"] == region]

    def findPlayer(self, tag, region, yesterday):
        ## format the data
        region = parseRegion(region)

        tag = self.getFormattedTag(tag)

        table = self.yesterday_table if yesterday else self.table

        ## check if tag on leaderboard
        player_data = self.getPlayerData(tag, table, region)

        ## check if tag has an alias since no data was found
        if len(player_data) == 0 and tag in self.alias:
            tag = self.alias[tag]
            player_data = self.getPlayerData(tag, table, region)

        if len(player_data) > 0:
            return tag, region, player_data, ""

        ## check if easter egg before digit because of numerical eggs
        if tag in eggs:
            return tag, region, [], eggs[tag]

        ## check if is digit
        if tag.isdigit():  ## jump to search by number
            num = int(tag)
            if num <= 1000 and num >= 1 and region is not None:
                player_data = self.getEntryFromRank(num, region, yesterday)
                return tag, region, player_data, ""
            elif num > 1000 or num < 1:
                return tag, region, [], "I only track the top 1000 players"
            else:
                return (
                    tag,
                    region,
                    [],
                    f"You must provide a region after the number i.e. !bgrank {num} na",
                )

        ## return nothing
        return (
            tag,
            region,
            [],
            f'{tag} {"is" if not yesterday else "was"} not on {printRegion(region) if region else "any BG"} leaderboards liiCat',
        )

    def formatRankText(self, yesterday, player_data):
        highestRank = 9999
        for item in player_data:
            if item["Rank"] < highestRank and item["Rank"] >= 1:
                tag = item["PlayerName"]
                highestRank = item["Rank"]
                rank = item["Rank"]
                region = printRegion(item["Region"])

                if len(item["Ratings"]) <= 0:
                    break

                rating = item["Ratings"][-1]

                # if item["Rank"] < 0:
                #     text = f'{tag} dropped from the {region} leaderboards but was {rating} mmr earlier {"today" if not yesterday else "Yesterday"} liiCat'
                # else:
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

        for item in player_data:
            if len(item["Ratings"]) > longestRecord:
                tag = item["PlayerName"]
                longestRecord = len(item["Ratings"])
                ratings = item["Ratings"]
                region = printRegion(item["Region"])

                emote = "liiHappyCat" if ratings[-1] > ratings[0] else "liiCat"

                text = (
                    f"{tag} started {'today' if not yesterday else 'yesterday'} at {ratings[0]} in {region} and {'is now ' if not yesterday else 'ended at ' }"
                    f"{ratings[-1]} with {self.getGamesPlayedFromDeltas(self.getDeltas(ratings))} games played. {emote} Their record {'is' if not yesterday else 'was'}: {self.getDeltas(ratings)}"
                )
        return text

    def getGamesPlayedFromDeltas(self, deltas):
        if not deltas:
            return 0
        else:
            return deltas.count(",") + 1

    def getDailyStatsText(self, tag, region=None, yesterday=False):
        tag, region, player_data, msg = self.findPlayer(tag, region, yesterday)
        if len(player_data) > 0:
            return self.formatDailyStatsText(yesterday, player_data)
        elif len(msg) > 0:
            return msg
        else:
            return help_text

    def getLeaderboardThreshold(self, rank=1000):
        table = self.table
        response = table.scan(
            FilterExpression=Attr("Rank").eq(rank),
        )

        dict = {}

        for item in response["Items"]:
            region = item["Region"]
            rating = item["Ratings"][-1]
            dict[region] = rating

        return dict

    def get_leaderboard_range(self, start_rank, end_rank):
        """
        Given a start_rank and end_rank, for each region, return a list of players in descending order between those ranks, inclusive.
        """
        if start_rank > end_rank:
            raise ValueError(
                f"start_rank:{start_rank} must be greater than or equal to end_rank:{end_rank}"
            )

        # Scan the whole database, filter for players whose rank is between our desired ranks.
        # We don't have any partition keys or secondary indexes on the database, so we must scan.
        response = self.table.scan(
            FilterExpression=Attr("Rank").between(start_rank, end_rank),
        )

        dict = {}
        # Make a list for each region, add players of that region to the list.
        for item in response["Items"]:
            region = item["Region"]
            if region not in dict:
                dict[region] = []
            rank = item["Rank"]
            rating = item["Ratings"][-1]
            player_name = item["PlayerName"]
            delta = item["Ratings"][-1] - item["Ratings"][0]
            dict[region].append((rank, rating, player_name, delta))

        # Sort each region list by player's rank.
        for key in dict.keys():
            # When sorting a list of tuples, the default behavior is to use the first element of the tuples.
            # In this case, the first element is the player's rank. So we are sorting by rank in each region.
            dict[key].sort()

        return dict

    def getMostMMRChanged(self, num, highest):
        # For each entry in the leaderboard, get the tag, region and mmr change
        # At the end sort the entries by mmr change and return the top 5 people

        response = self.table.scan()
        items = response["Items"]

        climbers = []

        for item in items:
            if len(item["Ratings"]) > 0:
                obj = {
                    "Tag": item["PlayerName"],
                    "Region": item["Region"],
                    "Start": item["Ratings"][0],
                    "End": item["Ratings"][-1],
                    "Change": int(item["Ratings"][-1] - item["Ratings"][0]),
                }

                climbers.append(obj)

        climbers.sort(key=lambda x: x["Change"], reverse=highest)

        try:
            return climbers[0:num]
        except:
            return []

    def getHardcoreGamers(self, num):
        response = self.table.scan()
        items = response["Items"]

        gamers = []

        for item in items:
            ratings = item["Ratings"]
            gameCount = self.getGamesPlayedFromDeltas(self.getDeltas(ratings))

            obj = {
                "Tag": item["PlayerName"],
                "Region": item["Region"],
                "Gamecount": gameCount,
            }

            gamers.append(obj)

        gamers.sort(key=lambda x: x["Gamecount"], reverse=True)

        try:
            return gamers[0:num]
        except:
            return []

    def getHighestRatingAndActivePlayers(self, num):
        response = self.table.scan()
        items = response["Items"]

        highest = []

        for item in items:
            if len(item["Ratings"]) > 0:
                ratings = item["Ratings"]

                obj = {
                    "Tag": item["PlayerName"],
                    "Region": item["Region"],
                    "Start": item["Ratings"][0],
                    "End": item["Ratings"][-1],
                    "Gamecount": len(ratings),
                    "Change": int(item["Ratings"][-1] - item["Ratings"][0]),
                }

                if len(ratings) > 1:
                    highest.append(obj)

        highest.sort(key=lambda x: x["End"], reverse=True)

        try:
            return highest[0:num]
        except:
            return []

    # This should only get called if ratings has more than 1 entry
    def getDeltas(self, ratings):
        lastRating = ratings[0]
        deltas = []

        for rating in ratings[1:]:
            delta = int(rating - lastRating)
            deltas.append("{0:+d}".format(delta))

            lastRating = rating

        self.removeRepeatDeltas(deltas)
        self.removePlusOneMinusOne(deltas)

        return ", ".join(deltas)

    # The leaderboard API will randomly give stale data resulting in +x, -x, +x, -x, +x occasionally after a +x game
    def removeRepeatDeltas(self, deltas):
        for i in reversed(range(len(deltas) - 1)):
            if (
                i < len(deltas) - 2
                and deltas[i] == deltas[i + 2]
                and int(deltas[i + 1]) == -1 * int(deltas[i])
            ):
                del deltas[i + 2]
                del deltas[i + 1]

        return deltas

    # The leaderboard API will randomly round up and down on MMR sometimes so this removes +1, -1, +1, -1 from the daily text
    def removePlusOneMinusOne(self, deltas):
        for i in reversed(range(len(deltas) - 1)):
            if i < len(deltas) - 1 and int(deltas[i]) == -1 * int(deltas[i + 1]):
                del deltas[i + 1]
                del deltas[i]

    def clearDailyTable(self):
        today_scan = self.table.scan()

        # Delete the entire today table
        with self.table.batch_writer() as batch:
            for each in today_scan["Items"]:
                batch.delete_item(
                    Key={"PlayerName": each["PlayerName"], "Region": each["Region"]}
                )

    def updateAlias(self):
        response = self.alias_table.scan()
        self.alias = {it["Alias"]: it["PlayerName"] for it in response["Items"]}

    def getChannels(self):
        response = self.channel_table.scan()
        return {it["ChannelName"]: it["PlayerName"] for it in response["Items"]}

    def addChannel(self, channel, playerName, new=True):
        item = {
            "ChannelName": channel,
            "PlayerName": playerName,
        }
        if new:
            item["New"] = new

        self.addAlias(channel, playerName)

        self.channel_table.put_item(Item=item)

    def addAlias(self, alias, playerName, new=True):
        item = {
            "Alias": alias,
            "PlayerName": playerName,
        }

        self.alias[alias] = playerName

        if new:
            item["New"] = new
        self.alias_table.put_item(Item=item)

    def deleteAlias(self, alias):
        key = {
            "Alias": alias,
        }
        response = self.alias_table.get_item(Key=key)
        if "Item" in response:
            self.alias_table.delete_item(Key=key)
        if alias in self.alias:
            del self.alias[alias]

    def deleteChannel(self, channel):
        key = {
            "ChannelName": channel,
        }
        self.channel_table.delete_item(Key=key)

    def getNewChannels(self):
        response = self.channel_table.scan(
            FilterExpression=Attr("New").eq(True),
        )
        with self.channel_table.batch_writer() as batch:
            for item in response["Items"]:
                item.pop("New", None)
                batch.put_item(item)
        return {it["ChannelName"]: it["PlayerName"] for it in response["Items"]}

    def getNewAlias(self):
        response = self.alias_table.scan(
            FilterExpression=Attr("New").eq(True),
        )
        with self.alias_table.batch_writer() as batch:
            for item in response["Items"]:
                item.pop("New", None)
                batch.put_item(item)

                self.alias[item["Alias"]] = item["PlayerName"]
        return self.alias

    def addDefaultAlias(self):
        for key in default_alias:
            self.addAlias(key, default_alias[key], False)

    def addChannels(self):
        for key in default_channels:
            self.addChannel(key, default_channels[key], False)

    async def fetchPatchLink(self):
        # URL of the API
        api_url = "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=4"

        # Send a request to fetch the JSON data from the API
        response = requests.get(api_url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()

            # Loop through each article in the data
            for article in data:
                content = article.get("content", "")  # Extract the content field
                # Check if 'battlegrounds' is mentioned in the content
                if "battlegrounds" in content.lower():
                    # Extract and print the article's 'defaultUrl'
                    article_url = article.get("defaultUrl")
                    self.patch_link = f"{article_url}"
                    break
            else:
                print("No article containing 'battlegrounds' found.")
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")
