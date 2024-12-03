import os
from datetime import datetime

import aiocron
import boto3
import requests
from botocore.config import Config
from dotenv import load_dotenv

from default_alias import alias as default_alias
from default_channels import channels as default_channels
from leaderboard_queries import (
    get_most_active_player,
    get_player_by_rank,
    get_player_mmr_changes,
    get_player_stats,
    get_weekly_progress,
)
from logger import setup_logger
from parseRegion import isServer, parseServer

eggs = {  # Easter eggs
    "salami": "salami is rank 69 in Antarctica with 16969 mmr CORM",
    "gomez": "gomez is a cat, cats do not play BG",
    "16969": "salami is rank 69 in Antarctica with 16969 mmr CORM",
}

help_msg = "@liiHS I had an issue, send help liiWait"

logger = setup_logger("leaderboardBot")


class LeaderboardBot:
    def __init__(self, table_name="HearthstoneLeaderboard", **kwargs):
        # Load AWS credentials from .env
        load_dotenv()

        # Configure AWS client for alias and channel tables
        config = Config(
            region_name="us-east-1",
            retries={"max_attempts": 1, "mode": "standard"},
            connect_timeout=5,
            read_timeout=5,
        )
        aws_dynamodb = boto3.resource(
            "dynamodb",
            config=config,
            region_name="us-east-1",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url="https://dynamodb.us-east-1.amazonaws.com",
            use_ssl=True,
            verify=True,
        )

        # Configure local client for leaderboard table
        if os.getenv("DYNAMODB_ENDPOINT"):  # Local development
            self.dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=os.getenv("DYNAMODB_ENDPOINT"),
                region_name="us-east-1",
                aws_access_key_id="dummy",
                aws_secret_access_key="dummy",
            )
        else:  # AWS environment
            self.dynamodb = aws_dynamodb

        self.table = self.dynamodb.Table(table_name)
        self.alias_table = aws_dynamodb.Table("player-alias-table")  # Always use AWS
        self.channel_table = aws_dynamodb.Table("channel-table")  # Always use AWS
        self.patch_link = "Waiting to fetch latest post..."
        self.updateAlias()
        aiocron.crontab("* * * * *", func=self.fetchPatchLink)

    def parseArgs(self, default, *args):
        """Parse command arguments, handling server and player name"""
        args = list(args)
        print(f"Debug - parseArgs input: {args}")

        for i, arg in enumerate(args):
            if len(arg) > 0 and ("/" == arg[0] or "!" == arg[0]):
                return ["Please don't try to hack me", None]

        if len(args) == 0 or args[0] == "\U000e0000":
            return [default, None]
        elif len(args) == 1:
            if isServer(args[0]):
                result = [default, parseServer(args[0])]
                print(f"Debug - Single arg (server): {result}")
                return result
            else:
                result = [args[0], None]
                print(f"Debug - Single arg (name): {result}")
                return result
        else:
            if isServer(args[1]):
                result = [args[0], parseServer(args[1])]
                print(f"Debug - Two args (name, server): {result}")
                return result
            elif isServer(args[0]):
                result = [args[1], parseServer(args[0])]
                print(f"Debug - Two args (server, name): {result}")
                return result
            else:
                result = [args[0], None]
                print(f"Debug - Two args (no server): {result}")
                return result

    def get_rank(self, tag, region=None, game_type="battlegrounds"):
        """Get player's current rank and MMR"""
        print(f"Debug - Initial region: {region}")  # Debug print

        # Handle aliases
        if tag in self.alias:
            tag = self.alias[tag]
            print(f"Debug - Found alias: {tag}")  # Debug print

        # Handle easter eggs
        if tag in eggs:
            return eggs[tag]

        # Handle rank lookups
        if tag.isdigit():
            rank = int(tag)
            if rank <= 1000 and rank >= 1:
                if region is None:
                    return f"You must provide a region after the number i.e. !{game_type}rank {{rank}} na"
                result = get_player_by_rank(rank, region, game_type=game_type)
                return self.format_rank_response(result)
            else:
                return "I only track the top 1000 players"

        # Handle player lookups
        print(
            f"Debug - Looking up player {tag} in region {region} for {game_type}"
        )  # Debug print
        result = get_player_stats(tag.lower(), region, game_type=game_type)
        print(f"Debug - Got result: {result}")  # Debug print
        return self.format_rank_response(result)

    def get_daily_stats(self, tag, region=None, game_type="battlegrounds"):
        """Get player's MMR changes for today"""
        if tag in self.alias:
            tag = self.alias[tag]

        if tag in eggs:
            return eggs[tag]

        logger.info("Getting daily stats for %s", tag)
        result = get_player_mmr_changes(tag.lower(), region, game_type=game_type)
        return self.format_daily_response(result)

    def get_weekly_stats(self, tag, region=None, game_type="battlegrounds"):
        """Get player's weekly progress"""
        if tag in self.alias:
            tag = self.alias[tag]

        if tag in eggs:
            return eggs[tag]

        result = get_weekly_progress(tag, region, game_type=game_type)

        # If result is a string, it's an error message
        if isinstance(result, str):
            return result + " TEST"  # Add TEST suffix for testing

        # Otherwise format the weekly stats as before
        return self.format_weekly_response(result)

    def format_rank_response(self, result):
        """Format rank query results for Twitch chat"""
        print(f"Debug - Formatting response: {result}")  # Add debug print
        if isinstance(result, str):  # Error message
            return result

        response = f"{result['name']} is rank {result['rank']} in {result['server']} with {result['rating']} mmr liiHappyCat"
        print(f"Debug - Formatted response: {response}")  # Add debug print
        return response

    def format_daily_response(self, result):
        """Format daily stats for Twitch chat"""
        if isinstance(result, str):
            return result

        if result["num_games"] == 0:
            # Get current stats when no games played
            current_stats = get_player_stats(
                result["name"], result["server"], game_type=result["game_type"]
            )
            if isinstance(current_stats, str):  # Error occurred getting stats
                return f"{result['name']} hasn't played any games today on {result['server']} liiCat"

            return (
                f"{result['name']} is rank {current_stats['rank']} in {result['server']} "
                f"with {current_stats['rating']} mmr liiHappyCat and has not played any games today liiCat"
            )

        emote = "liiHappyCat" if result["net_change"] > 0 else "liiCat"
        net_change_str = (
            f"+{result['net_change']}"
            if result["net_change"] > 0
            else str(result["net_change"])
        )
        return (
            f"{result['name']} started today at {result['initial_mmr']} in {result['server']} "
            f"and is now {result['final_mmr']} ({net_change_str}) with {result['num_games']} games played. {emote} "
            f"Their record is: {', '.join(str(x) for x in result['mmr_changes'])}"
        )

    def format_weekly_response(self, result):
        """Format weekly progress for Twitch chat"""
        if result["start_mmr"] is None:
            return f"No data found for {result['player_name']} in the past week"

        emote = "liiHappyCat" if result["total_net_change"] > 0 else "liiCat"
        changes = [
            f"+{c['net_change']}" if c["net_change"] > 0 else str(c["net_change"])
            for c in result["daily_progress"]
        ]

        return (
            f"{result['player_name']} this week: {result['start_mmr']} → {result['end_mmr']} "
            f"MMR ({result['total_net_change']}) {emote} [{', '.join(changes)}]"
        )

    # Keep existing alias and channel management functions
    def updateAlias(self):
        try:
            response = self.alias_table.scan()
            self.alias = {it["Alias"]: it["PlayerName"] for it in response["Items"]}
        except Exception as e:
            print(f"Warning: Could not load aliases from AWS: {e}")
            # Use default aliases if AWS table is not available
            self.alias = default_alias

    def getChannels(self):
        try:
            response = self.channel_table.scan()
            return {it["ChannelName"]: it["PlayerName"] for it in response["Items"]}
        except Exception as e:
            print(f"Warning: Could not load channels from AWS: {e}")
            # Use default channels if AWS table is not available
            return default_channels

    async def fetchPatchLink(self):
        # Existing patch notes fetching code...
        pass

    def getNewAlias(self):
        """Get new aliases from AWS and add them to the local cache"""
        try:
            response = self.alias_table.scan(
                FilterExpression="attribute_exists(#new)",
                ExpressionAttributeNames={"#new": "New"},
            )

            # Update local cache with new aliases
            for item in response["Items"]:
                self.alias[item["Alias"]] = item["PlayerName"]

            # Remove 'New' attribute from processed items
            with self.alias_table.batch_writer() as batch:
                for item in response["Items"]:
                    item.pop("New", None)
                    batch.put_item(item)

            return self.alias
        except Exception as e:
            print(f"Warning: Could not fetch new aliases from AWS: {e}")
            return {}
