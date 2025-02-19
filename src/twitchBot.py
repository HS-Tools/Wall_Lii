import argparse
import os
import aiocron
import boto3
import asyncio
import aiohttp
from typing import List, Set
import time
from dotenv import load_dotenv
import requests
from twitchio.ext import commands

from leaderboard_queries import LeaderboardDB
from logger import setup_logger
from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict, get_trinkets_dict, parse_buddy, parse_trinket
from command_logger import CommandLogger, command_timer

logger = setup_logger("twitchBot")

# Load environment variables
load_dotenv()


def clean_input(user_input):
    """Cleans user input to remove any unwanted characters or prefixes."""
    # Remove invisible characters and leading/trailing whitespace
    if not user_input:
        return None
    cleaned = "".join(c for c in user_input if c.isprintable()).strip()

    # Remove leading '!' to prevent commands
    if cleaned.startswith("!"):
        cleaned = cleaned.lstrip("!")  # Removes all leading '!' characters

    print(cleaned)

    return cleaned


class CooldownManager:
    def __init__(self, cooldown_channels: Set[str], cooldown_seconds: int = 10):
        self.cooldown_channels = cooldown_channels
        self.cooldown_seconds = cooldown_seconds
        self.last_command_time: Dict[str, float] = {}

    def can_execute(self, channel: str) -> bool:
        """Check if a command can be executed in the given channel"""
        if channel not in self.cooldown_channels:
            return True
            
        current_time = time.time()
        last_time = self.last_command_time.get(channel, 0)
        
        return current_time - last_time >= self.cooldown_seconds

    def update_last_command(self, channel: str):
        """Update the last command time for a channel"""
        self.last_command_time[channel] = time.time()


class LeaderboardBot(commands.Bot):
    def __init__(self, token, prefix, initial_channels):
        # Initialize bot with environment variables
        self.db = LeaderboardDB(table_name="HearthstoneLeaderboardV2")
        
        # Configure AWS client for channel table
        aws_kwargs = {
            "region_name": "us-east-1",
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        }
        
        # Initialize DynamoDB resource
        self.dynamodb = boto3.resource("dynamodb", **aws_kwargs)
        self.channel_table = self.dynamodb.Table("channel-table")
        
        # Track all known channels and currently joined channels
        self.all_channels = set()
        self.joined_channels = set()
        self.priority_channels = {"liihs", "jeefhs", "beterbabbit", "dogdog", "rdulive", "xqn_thesad", "superjj102"}  # These channels are always joined
        self._load_channels()
        
        # Initialize cooldown manager with channels that need cooldown
        self.cooldown_manager = CooldownManager({"superjj102"}, 10)  # 10 second cooldown for specified channels
        
        # Check if we have necessary Twitch API credentials
        if not os.environ.get("CLIENT_ID") or not os.environ.get("TMI_TOKEN"):
            logger.error("Missing Twitch API credentials. Please set CLIENT_ID and TMI_TOKEN in .env")
            raise ValueError("Missing Twitch API credentials")
        
        # Initialize bot with priority channels
        super().__init__(
            token=token,
            irc_token=token,
            client_id=os.environ["CLIENT_ID"],
            nick=os.environ["BOT_NICK"],
            prefix=prefix,
            initial_channels=list(self.priority_channels)
        )
        
        # Initialize command logger
        self.command_logger = CommandLogger()
        
        # Initialize buddy and trinket dictionaries
        self.buddy_dict = get_buddy_dict()
        self.trinket_dict = get_trinkets_dict()
        
        # Add cron job for updating daily leaderboards every hour
        self.update_leaderboards_cron = aiocron.crontab('59 * * * *', func=self.update_leaderboards)
        # Set up cron job to update channels every minute
        self.channel_cron = aiocron.crontab("*/1 * * * *", func=self.update_live_channels)
        
    async def update_leaderboards(self):
        """Update daily leaderboards every hour"""
        try:
            self.db.update_daily_leaderboards()
            logger.info("Successfully updated daily leaderboards via cron job")
        except Exception as e:
            logger.error(f"Error updating daily leaderboards via cron job: {e}")

    def _load_channels(self):
        """Load channels from DynamoDB table"""
        try:
            response = self.channel_table.scan()
            self.all_channels = {item["ChannelName"].lower() for item in response.get("Items", [])}
        except Exception as e:
            logger.error(f"Failed to load channels from DynamoDB: {e}")
            self.all_channels = {"liihs"}

    async def _get_live_channels(self, channels: Set[str]) -> Set[str]:
        """Get list of currently live channels"""
        if not channels:
            return set()

        # Twitch API requires user IDs, so first get user IDs for all channels
        headers = {
            'Client-ID': os.environ["TWITCH_CLIENT_ID"],
            'Authorization': f'Bearer {os.environ["TWITCH_TOKEN"]}'
        }

        async with aiohttp.ClientSession() as session:
            live_channels = set()
            channel_list = list(channels)
            
            # Process in smaller batches of 50 to be safer
            for i in range(0, len(channel_list), 50):
                batch = channel_list[i:i + 50]
                query_params = "&".join([f"user_login={channel}" for channel in batch])
                url = f'https://api.twitch.tv/helix/streams?{query_params}'
                
                try:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            live_channels.update(stream['user_login'].lower() for stream in data['data'])
                        else:
                            error_text = await response.text()
                            logger.error(f"API request failed with status {response.status}: {error_text}")
                            # If we get an error, try one by one for this batch
                            for channel in batch:
                                try:
                                    single_url = f'https://api.twitch.tv/helix/streams?user_login={channel}'
                                    async with session.get(single_url, headers=headers) as single_response:
                                        if single_response.status == 200:
                                            data = await single_response.json()
                                            if data['data']:  # If stream is live
                                                live_channels.add(channel.lower())
                                except Exception as e:
                                    logger.error(f"Error checking single channel {channel}: {e}")
                except Exception as e:
                    logger.error(f"Error checking batch of channels: {e}")
                
                # Add a small delay between batches to avoid rate limits
                await asyncio.sleep(0.1)

        logger.info(f"Found {len(live_channels)} live channels: {live_channels}")
        return live_channels

    async def update_live_channels(self):
        """Update which channels we're joined to based on live status"""
        try:
            # Refresh channel list from DynamoDB
            self._load_channels()
            
            # Get currently live channels
            live_channels = await self._get_live_channels(self.all_channels)
            
            # Add priority channels to live channels
            channels_to_monitor = live_channels.union(self.priority_channels)
            logger.info(f"Channels to monitor: {channels_to_monitor}")
            
            # Determine which channels to join/leave
            channels_to_join = channels_to_monitor - self.joined_channels
            channels_to_leave = self.joined_channels - channels_to_monitor
            
            logger.info(f"Channels to join: {channels_to_join}")
            logger.info(f"Channels to leave: {channels_to_leave}")
            
            # Join new live channels
            if channels_to_join:
                try:
                    await super().join_channels(list(channels_to_join))
                    self.joined_channels.update(channels_to_join)
                except Exception as e:
                    logger.error(f"Error joining channels: {e}")
            
            # Leave offline channels (except priority channels)
            if channels_to_leave:
                try:
                    await super().part_channels(list(channels_to_leave))
                    self.joined_channels.difference_update(channels_to_leave)
                except Exception as e:
                    logger.error(f"Error leaving channels: {e}")
                    
        except Exception as e:
            logger.error(f"Error in update_live_channels: {e}")

    async def join_channels(self, channels, rate_limit=20, interval=30):
        """Join channels in batches to respect rate limits"""
        for i in range(0, len(channels), rate_limit):
            batch = channels[i:i + rate_limit]
            print(f"Joining channels: {batch}")
            await super().join_channels(batch)
            await asyncio.sleep(interval)  # Throttle to avoid rate limit

    async def event_ready(self):
        logger.info(f"Bot ready | {self.nick}")
        # Initial channel update
        await self.update_live_channels()

    def _parse_rank_and_server(self, arg1, arg2):
        """
        Parse rank and server from command arguments, supporting both formats:
        !command rank server and !command server rank
        """
        servers = {"na", "eu", "ap"}
        arg1 = clean_input(arg1)
        arg2 = clean_input(arg2)
        
        if not arg1:
            return None, None
            
        # Check if arg1 is a server
        if arg1.lower() in servers:
            # Format: !command server rank
            return arg2, arg1
        else:
            # Format: !command rank server
            return arg1, arg2

    async def _handle_command(self, ctx, coro):
        """Wrapper to handle command execution with cooldown"""
        channel = ctx.channel.name.lower()
        
        if not self.cooldown_manager.can_execute(channel):
            # Skip command execution if on cooldown
            return
            
        try:
            await coro
            # Update cooldown only if command executed successfully
            self.cooldown_manager.update_last_command(channel)
        except Exception as e:
            logger.error(f"Error executing command in {channel}: {e}")

    @commands.command(name="rank", aliases=["bgrank", "duorank"])
    @command_timer
    async def rank_command(self, ctx, arg1=None, arg2=None):
        """Get player rank, defaulting to channel name if no player specified"""
        await self._handle_command(ctx, self._rank_command_impl(ctx, arg1, arg2))

    async def _rank_command_impl(self, ctx, arg1, arg2):
        player_or_rank, server = self._parse_rank_and_server(arg1, arg2)
        
        if player_or_rank is None:
            player_or_rank = ctx.channel.name
            
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!')
        game_mode = "1" if command_used == "duorank" else "0"
        
        if player_or_rank.isdigit() and (server is None or server == ""):
            # No server specified, get players at the specified rank for all servers
            servers = ["NA", "EU", "AP"]
            responses = []
            for srv in servers:
                response = self.db.format_player_stats(player_or_rank, srv, game_mode)
                if "No player found" not in response:
                    responses.append(response)
            await ctx.send(" | ".join(responses))
        else:
            # Regular player or rank lookup
            response = self.db.format_player_stats(player_or_rank, server, game_mode)
            await ctx.send(response)

    @commands.command(name="day", aliases=["bgdaily", "daily", "duoday", "duodaily"])
    @command_timer
    async def day_command(self, ctx, arg1=None, arg2=None):
        """Get player's daily stats for both regular and duo modes"""
        await self._handle_command(ctx, self._day_command_impl(ctx, arg1, arg2))

    async def _day_command_impl(self, ctx, arg1, arg2):
        player_or_rank, server = self._parse_rank_and_server(arg1, arg2)
        
        if player_or_rank is None:
            player_or_rank = ctx.channel.name
            
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!')
        game_mode = "1" if command_used == "duodaily" or command_used == "duoday" else "0"
        
        response = self.db.format_daily_stats(player_or_rank, server, game_mode)
        await ctx.send(response)

    @commands.command(name="yesterday", aliases=["bgyesterday", "duoyesterday", "yday", "duoyday"])
    @command_timer
    async def yesterday_command(self, ctx, arg1=None, arg2=None):
        """Get player's stats for yesterday for both regular and duo modes"""
        await self._handle_command(ctx, self._yesterday_command_impl(ctx, arg1, arg2))

    async def _yesterday_command_impl(self, ctx, arg1, arg2):
        player_or_rank, server = self._parse_rank_and_server(arg1, arg2)
        
        if player_or_rank is None:
            player_or_rank = ctx.channel.name
            
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!')
        game_mode = "1" if command_used == "duoyesterday" or command_used == "duoyday" else "0"
        
        response = self.db.format_yesterday_stats(player_or_rank, server, game_mode)
        await ctx.send(response)

    @commands.command(name="week", aliases=["bgweekly", "duoweek", "duoweekly"])
    @command_timer
    async def week_command(self, ctx, arg1=None, arg2=None):
        """Get player's weekly stats for both regular and duo modes"""
        await self._handle_command(ctx, self._week_command_impl(ctx, arg1, arg2))

    async def _week_command_impl(self, ctx, arg1, arg2):
        player_or_rank, server = self._parse_rank_and_server(arg1, arg2)
        
        if player_or_rank is None:
            player_or_rank = ctx.channel.name
            
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!')
        game_mode = "1" if command_used == "duoweek" or command_used == "duoweekly" else "0"
        
        response = self.db.format_weekly_stats(player_or_rank, server, game_mode)
        await ctx.send(response)

    @commands.command(name="lastweek", aliases=["bglastweek", "duolastweek", "lweek", "duolweek"])
    @command_timer
    async def lastweek_command(self, ctx, arg1=None, arg2=None):
        """Get player's stats for last week for both regular and duo modes"""
        await self._handle_command(ctx, self._lastweek_command_impl(ctx, arg1, arg2))

    async def _lastweek_command_impl(self, ctx, arg1, arg2):
        player_or_rank, server = self._parse_rank_and_server(arg1, arg2)
        
        if player_or_rank is None:
            player_or_rank = ctx.channel.name
            
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!')
        game_mode = "1" if command_used.startswith("duo") else "0"
        
        response = self.db.format_last_week_stats(player_or_rank, server, game_mode)
        await ctx.send(response)

    @commands.command(name="peak", aliases=["duopeak"])
    @command_timer
    async def peak_command(self, ctx, arg1=None, arg2=None):
        """Get player's peak rating for both regular and duo modes"""
        await self._handle_command(ctx, self._peak_command_impl(ctx, arg1, arg2))

    async def _peak_command_impl(self, ctx, arg1, arg2):
        player_or_rank, server = self._parse_rank_and_server(arg1, arg2)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name

        server = clean_input(server)
        
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!');
        game_mode = "1" if command_used == "duopeak" else "0"
        
        response = self.db.format_peak_stats(player_or_rank, server, game_mode)
        await ctx.send(response)

    @commands.command(name="stats", aliases=["bgstats", "duostats"])
    @command_timer
    async def stats(self, ctx, server=None):
        """Display server stats, or all servers if no server specified"""
        await self._handle_command(ctx, self._stats_impl(ctx, server))

    async def _stats_impl(self, ctx, server):
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!');
        game_mode = "1" if command_used == "duostats" else "0"

        server = clean_input(server)
        if server is None or server == "":
            # No server specified, get stats for all servers
            servers = ["NA", "EU", "AP"]
            responses = []
            for srv in servers:
                response = self.db.format_region_stats(srv, game_mode)
                if "No stats available" not in response:
                    # Omit the maximum MMR part
                    response = response.split(". The highest rating is")[0]
                    responses.append(response)
            await ctx.send(" | ".join(responses))
        else:
            # Server specified, get stats for that server
            server = clean_input(server)
            response = self.db.format_region_stats(server, game_mode)
            await ctx.send(response)

    @commands.command(name="top", aliases=["bgtop", "duotop"])
    @command_timer
    async def bgtop(self, ctx, server=None):
        """Display top players, or top globally if no server specified"""
        await self._handle_command(ctx, self._bgtop_impl(ctx, server))

    async def _bgtop_impl(self, ctx, server):
        # Determine game mode based on command used
        command_used = ctx.message.content.split()[0].lstrip('!');
        game_mode = "1" if command_used == "duotop" else "0"

        server = clean_input(server)
        if server is None or server == "":
            # No server specified, get top players globally
            response = self.db.format_top_players_global(game_mode)
            await ctx.send(response)
        else:
            # Server specified, get top players for that server
            server = clean_input(server)
            response = self.db.format_top_players(server, game_mode)

            await ctx.send(response)

    @commands.command(name="help", aliases=["commands", "wall_lii"])
    @command_timer
    async def help_command(self, ctx, command_name=None):
        """Display help information for commands"""
        await self._handle_command(ctx, self._help_command_impl(ctx, command_name))

    async def _help_command_impl(self, ctx, command_name):
        if clean_input(command_name) is None or clean_input(command_name) == "":
            # Base help message
            help_message = (
                "Available commands: !rank, !day, !week, !lastweek, !peak, !stats, !top, !origin, !yday "
                "Use `!help <command>` for detailed information on a specific command. "
                "A day resets at 00:00 PST. A week resets on Monday at 00:00 PST."
            )
            await ctx.send(help_message)
        else:
            # Specific help messages
            command_name = command_name.lower()
            help_messages = {
                "rank": (
                    "!rank [player] [server]: Get the rank of a player. "
                    "Use the optional 'duo' prefix for duos. "
                    "Defaults to the channel name if no player is specified. "
                    "Example: !rank lii NA or !duorank lii NA"
                ),
                "day": (
                    "!day [player] [server]: Get daily stats for a player. "
                    "Use the optional 'duo' prefix for duos. "
                    "Defaults to the channel name if no player is specified. "
                    "Example: !day lii NA or !duoday lii NA"
                ),
                "week": (
                    "!week [player] [server]: Get weekly stats for a player. "
                    "Use the optional 'duo' prefix for duos. "
                    "Defaults to the channel name if no player is specified. "
                    "Example: !week lii NA or !duoweek lii NA"
                ),
                "lastweek": (
                    "!lastweek [player] [server]: Get stats from the previous week for a player. "
                    "Use the optional 'duo' prefix for duos. "
                    "Defaults to the channel name if no player is specified. "
                    "Example: !lastweek lii NA or !duolastweek lii NA"
                ),
                "yday": (
                    "!yday [player] [server]: Get yesterday's stats for a player. "
                    "Use the optional 'duo' prefix for duos. "
                    "Defaults to the channel name if no player is specified. "
                    "Example: !yday lii NA or !duoyday lii NA"
                ),
                "peak": (
                    "!peak [player] [server]: Get the peak rating of a player. "
                    "Use the optional 'duo' prefix for duos. "
                    "Defaults to the channel name if no player is specified. "
                    "Example: !peak lii NA or !duopeak lii NA"
                ),
                "stats": (
                    "!stats [server]: Display server stats. "
                    "Use the optional 'duo' prefix for duos. "
                    "If no server is specified, stats for all servers are shown. "
                    "Example: !stats NA or !duostats NA"
                ),
                "top": (
                    "![duo]top [server]: Display top players. "
                    "Use the optional 'duo' prefix for duos. "
                    "If no server is specified, top players globally are shown. "
                    "Example: !top NA or !duotop NA"
                ),
            }

            # Send specific help message or default if command not found
            await ctx.send(help_messages.get(command_name, "Command not found. Use `!help` to see available commands."))

    @commands.command(name="8k")
    @command_timer
    async def eight_k(self, ctx, server=None):
        """Show first player to reach 8000 rating"""
        await self._handle_command(ctx, self._eight_k_impl(ctx, server))

    async def _eight_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(8000, server)
        await ctx.send(response)

    @commands.command(name="9k")
    @command_timer
    async def nine_k(self, ctx, server=None):
        """Show first player to reach 9000 rating"""
        await self._handle_command(ctx, self._nine_k_impl(ctx, server))

    async def _nine_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(9000, server)
        await ctx.send(response)

    @commands.command(name="10k")
    @command_timer
    async def ten_k(self, ctx, server=None):

        await self._handle_command(ctx, self._ten_k_impl(ctx, server))

    async def _ten_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(10000, server)
        await ctx.send(response)

    @commands.command(name="11k")
    @command_timer
    async def eleven_k(self, ctx, server=None):
        await self._handle_command(ctx, self._eleven_k_impl(ctx, server))

    async def _eleven_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(11000, server)
        await ctx.send(response)

    @commands.command(name="12k")
    @command_timer
    async def twelve_k(self, ctx, server=None):
        await self._handle_command(ctx, self._twelve_k_impl(ctx, server))

    async def _twelve_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(12000, server)
        await ctx.send(response)

    @commands.command(name="13k")
    @command_timer
    async def thirteen_k(self, ctx, server=None):
        await self._handle_command(ctx, self._thirteen_k_impl(ctx, server))

    async def _thirteen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(13000, server)
        await ctx.send(response)

    @commands.command(name="14k")
    @command_timer
    async def fourteen_k(self, ctx, server=None):
        await self._handle_command(ctx, self._fourteen_k_impl(ctx, server))

    async def _fourteen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(14000, server)
        await ctx.send(response)

    @commands.command(name="15k")
    @command_timer
    async def fifteen_k(self, ctx, server=None):

        await self._handle_command(ctx, self._fifteen_k_impl(ctx, server))

    async def _fifteen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(15000, server)
        await ctx.send(response)

    @commands.command(name="16k")
    @command_timer
    async def sixteen_k(self, ctx, server=None):
        await self._handle_command(ctx, self._sixteen_k_impl(ctx, server))

    async def _sixteen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(16000, server)
        await ctx.send(response)

    @commands.command(name="17k")
    @command_timer
    async def seventeen_k(self, ctx, server=None):
        await self._handle_command(ctx, self._seventeen_k_impl(ctx, server))

    async def _seventeen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(17000, server)
        await ctx.send(response)

    @commands.command(name="18k")
    @command_timer
    async def eighteen_k(self, ctx, server=None):
        """Show first player to reach 18000 rating"""
        await self._handle_command(ctx, self._eighteen_k_impl(ctx, server))

    async def _eighteen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(18000, server)
        await ctx.send(response)

    @commands.command(name="19k")
    @command_timer
    async def nineteen_k(self, ctx, server=None):
        """Show first player to reach 19000 rating"""
        await self._handle_command(ctx, self._nineteen_k_impl(ctx, server))

    async def _nineteen_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(19000, server)
        await ctx.send(response)

    @commands.command(name="20k")
    @command_timer
    async def twenty_k(self, ctx, server=None):
        """Show first player to reach 20000 rating"""
        await self._handle_command(ctx, self._twenty_k_impl(ctx, server))

    async def _twenty_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(20000, server)
        await ctx.send(response)

    @commands.command(name="21k")
    @command_timer
    async def twentyone_k(self, ctx, server=None):
        """Show first player to reach 21000 rating"""
        await self._handle_command(ctx, self._twentyone_k_impl(ctx, server))

    async def _twentyone_k_impl(self, ctx, server):
        server = clean_input(server)
        response = self.db.format_milestone_stats(21000, server)
        await ctx.send(response)

    @commands.command(name="goodbot")
    @command_timer
    async def goodbot(self, ctx):
        """Respond to praise with a robotic acknowledgment"""
        await self._handle_command(ctx, self._goodbot_impl(ctx))

    async def _goodbot_impl(self, ctx):
        await ctx.send("MrDestructoid Just doing my job MrDestructoid")

    @commands.command(name="bgdailii")
    @command_timer
    async def bgdailii(self, ctx):
        """Show daily stats for liihs"""
        await self._handle_command(ctx, self._bgdailii_impl(ctx))

    async def _bgdailii_impl(self, ctx):
        response = self.db.format_daily_stats("liihs", "NA", "0")
        await ctx.send(response)

    @commands.command(name="weeklii")
    @command_timer
    async def weeklii(self, ctx):
        """Show weekly stats for liihs"""
        await self._handle_command(ctx, self._weeklii_impl(ctx))

    async def _weeklii_impl(self, ctx):
        response = self.db.format_weekly_stats("liihs", "NA", "0")
        await ctx.send(response)

    @commands.command(name="patch", aliases=["bgpatch"])
    @command_timer
    async def patch(self, ctx):
        """Fetch the latest patch notes link"""
        await self._handle_command(ctx, self._patch_impl(ctx))

    async def _patch_impl(self, ctx):
        await ctx.send(f"{self.db.get_patch_link()}")

    @commands.command(name="origin")
    @command_timer
    async def origin(self, ctx):
        await self._handle_command(ctx, self._origin_impl(ctx))

    async def _origin_impl(self, ctx):
        await ctx.send("I was created by twitch.tv/liihs to help track BG leaderboard stats. My code is here: https://github.com/HS-Tools/Wall_Lii")

    @commands.command(name="buddy")
    @command_timer
    async def buddy(self, ctx):
        """Get buddy information for a hero"""
        await self._handle_command(ctx, self._buddy_impl(ctx))

    async def _buddy_impl(self, ctx):
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            return

        buddy_name = args[1].lower()
        results = parse_buddy(buddy_name, self.buddy_dict, easter_egg_buddies_dict)

        if results:
            await ctx.send(results[1])  # Send regular buddy text

    @commands.command(name="goldenbuddy")
    @command_timer
    async def goldenbuddy(self, ctx):
        """Get golden buddy information for a hero"""
        if ctx.channel.name == "dogdog":  # Skip command in certain channels
            return
        await self._handle_command(ctx, self._goldenbuddy_impl(ctx))

    async def _goldenbuddy_impl(self, ctx):
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            return

        buddy_name = args[1].lower()
        results = parse_buddy(buddy_name, self.buddy_dict, easter_egg_buddies_dict)

        if results:
            await ctx.send(results[2])  # Send golden buddy text

    @commands.command(name="trinket")
    @command_timer
    async def trinket(self, ctx):
        """Get trinket information"""
        await self._handle_command(ctx, self._trinket_impl(ctx))

    async def _trinket_impl(self, ctx):
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            return

        trinket_name = " ".join(args[1:]).lower()
        results = parse_trinket(trinket_name, self.trinket_dict)

        if results:
            await ctx.send(results)

    @commands.command(name="buddygold")
    @command_timer
    async def buddygold(self, ctx):
        """Show gold cost for buddy tiers"""
        await self._handle_command(ctx, self._buddygold_impl(ctx))

    async def _buddygold_impl(self, ctx):
        tiers = {
            1: [11, 13],
            2: [13, 15],
            3: [15, 17],
            4: [17, 19],
            5: [19, 21],
            6: [21, 23],
        }
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            await ctx.send("Add a tier between 1 and 6 like !buddygold 3")
            return

        buddy_tier = args[1]
        if str.isdigit(buddy_tier) and 1 <= int(buddy_tier) <= 6:
            tier = int(buddy_tier)
            await ctx.send(
                f"A tier {tier} buddy has an initial cost of {tiers[tier][0]} "
                f"and a reset cost of {tiers[tier][1]}"
            )
        else:
            await ctx.send("Invalid tier, try a number between 1 and 6 like !buddygold 3")

    @commands.command(name="curves")
    @command_timer
    async def curves(self, ctx):
        """Link to BG curve sheet"""
        await self._handle_command(ctx, self._curves_impl(ctx))

    async def _curves_impl(self, ctx):
        await ctx.send("Check out www.BGcurvesheet.com for information about heroes and curves")

    @commands.command(name="shush", aliases=["Shush"])
    @command_timer
    async def shush(self, ctx):
        """Shush command"""
        await self._handle_command(ctx, self._shush_impl(ctx))

    async def _shush_impl(self, ctx):
        await ctx.send("Shush")

    @commands.command(name="frog", aliases=["Frog"])
    @command_timer
    async def frog(self, ctx):
        """Frog command"""
        await self._handle_command(ctx, self._frog_impl(ctx))

    async def _frog_impl(self, ctx):
        await ctx.send("liiPers liiPers liiPers")

    @commands.command(name="gold")
    @command_timer
    async def gold(self, ctx):
        """Calculate the turn when a quest requiring X gold will be completed"""
        await self._handle_command(ctx, self._gold_impl(ctx))

    async def _gold_impl(self, ctx):
        incorrect_use_text = "Use this command with the number of gold your quest requires: !gold 55"
        
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            await ctx.send(incorrect_use_text)
            return

        try:
            gold_amount = int(args[1])
        except ValueError:
            await ctx.send(incorrect_use_text)
            return

        # Calculate turn quest will be completed based on startingTurn and goldAmount
        starting_turn = 1
        max_gold = 10
        current_gold = starting_turn + 2
        turn = starting_turn

        # Cap current gold at max
        if current_gold > max_gold:
            current_gold = max_gold

        while gold_amount > current_gold:
            gold_amount -= current_gold
            turn += 1
            if current_gold < max_gold:
                current_gold += 1

        if turn > starting_turn:
            await ctx.send(
                f"{int(args[1])} gold will be spent by Turn {turn}, or Turn {turn - 1} if {gold_amount} extra gold is spent. Assuming quest is started on Turn {starting_turn}."
            )
        else:
            await ctx.send(f"{int(args[1])} gold will be spent by Turn {turn} if quest is started on Turn {starting_turn}.")

def main():
    global bot
    # Add command line arguments
    parser = argparse.ArgumentParser(
        description="Twitch Bot for Hearthstone BG Leaderboard"
    )
    parser.add_argument(
        "--aws", action="store_true", help="Use AWS DynamoDB instead of local"
    )
    args = parser.parse_args()

    # Load environment variables
    token = os.environ["TMI_TOKEN"]
    prefix = os.environ.get("BOT_PREFIX", "!")
    channels = os.environ.get("CHANNELS", "jimliu").split(",")

    # Initialize and run bot
    bot = LeaderboardBot(
        token=token, prefix=prefix, initial_channels=channels
    )
    bot.run()


if __name__ == "__main__":
    main()
