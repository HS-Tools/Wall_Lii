# managers/channel_manager.py

import os
import aiohttp
import asyncio
import boto3
from typing import Set
from logger import setup_logger
import re

VALID_TWITCH_USERNAME = re.compile(r"^[a-zA-Z0-9_]{4,25}$")
logger = setup_logger("ChannelManager")


class ChannelManager:
    def __init__(self, priority_channels: Set[str]):
        self.priority_channels = priority_channels
        self.all_channels = set()
        self.joined_channels = set()
        self.hearthstone_channels = set()

        # Setup AWS DynamoDB client
        aws_kwargs = {
            "region_name": "us-east-1",
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        }
        self.dynamodb = boto3.resource("dynamodb", **aws_kwargs)
        self.channel_table = self.dynamodb.Table("channel-table")

        # Load channels immediately
        self.load_channels()

    def load_channels(self):
        try:
            response = self.channel_table.scan()
            self.all_channels = {
                item["ChannelName"].strip().lower()
                for item in response.get("Items", [])
                if item.get("ChannelName")
                and VALID_TWITCH_USERNAME.match(item["ChannelName"].strip())
            }
            logger.info(f"Loaded {len(self.all_channels)} channels from DynamoDB")
        except Exception as e:
            logger.error(f"Failed to load channels from DynamoDB: {e}")
            self.all_channels = {"liihs"}

    async def get_live_channels(self, channels: Set[str]) -> Set[str]:
        if not channels:
            return set()

        try:
            headers = {
                "Client-ID": os.environ["TWITCH_CLIENT_ID"],
                "Authorization": f'Bearer {os.environ["TWITCH_TOKEN"]}',
            }
        except KeyError as e:
            logger.error(f"Missing environment variable: {e}")
            return set()

        async with aiohttp.ClientSession() as session:
            live_channels = set()
            self.hearthstone_channels = set()
            channel_list = [c for c in list(channels) if c and c.strip()]

            for i in range(0, len(channel_list), 50):
                batch = channel_list[i : i + 50]
                query_params = "&".join([f"user_login={channel}" for channel in batch])
                url = f"https://api.twitch.tv/helix/streams?{query_params}"

                try:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            for stream in data["data"]:
                                channel_name = stream["user_login"].lower()
                                live_channels.add(channel_name)
                                if (
                                    stream.get("game_id") == "138585"
                                    or stream.get("game_name", "").lower()
                                    == "hearthstone"
                                ):
                                    self.hearthstone_channels.add(channel_name)
                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"Batch failed: {response.status} - {error_text}"
                            )
                except Exception as e:
                    logger.error(f"Batch error: {e}")

                # Add a delay between batches to avoid rate limits
                await asyncio.sleep(0.5)

        logger.info(f"Live channels: {live_channels}")
        return live_channels

    async def update_live_channels(self, bot_instance):
        """This method is no longer used - channel joining is handled in TwitchBot"""
        logger.warning("update_live_channels called but is deprecated")
        pass
