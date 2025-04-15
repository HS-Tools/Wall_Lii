import os
import asyncio
from datetime import datetime
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pytz import timezone
from leaderboard import LeaderboardDB
from utils.aws_dynamodb import DynamoDBClient
from logger import setup_logger

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger("DiscordBot")

# Configure intents
intents = discord.Intents.default()
intents.message_content = True

# Discord IDs and channel configurations
CHANNEL_IDS = {
    "wall_lii": 811468284394209300,
    "wall-lii-requests": 846867129834930207,
    "test": 730782280674443327,
}

LII_DISCORD_ID = 729524538559430670
COMP_HS_DISCORD_ID = 939711967134887998
COMP_HS_DISCORD_CHANNEL_ID = 1242140313242566708
FRONTPAGE_CHANNEL_ID = 1096490528947851370
FRONTPAGE_MESSAGE_ID = 1096514937813217370

EMOTES = ["liiHappyCat", "liiCat", "ninaisFEESH", "liiWait"]


class DiscordBot(commands.Bot):
    def __init__(self):
        # Disable the default help command before creating the bot instance
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.db = LeaderboardDB()
        self.dynamo_client = DynamoDBClient()

        # Add event handlers
        self.add_event_handlers()

        # Register commands
        self.add_commands()

    def add_event_handlers(self):
        """Add event handlers for the bot"""

        @self.event
        async def on_ready():
            logger.info(f"Logged in as {self.user.name} ({self.user.id})")
            logger.info(f"Connected to {len(self.guilds)} guilds")

            # ❗ Clear global slash commands
            self.tree.clear_commands(guild=None)
            await self.tree.sync(guild=None)
            logger.info("Cleared global slash commands")

            # ❗ Clear slash commands for each guild the bot is in
            for guild in self.guilds:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Cleared slash commands for guild: {guild.name}")

        @self.event
        async def on_command_error(ctx, error):
            """Handle command errors"""
            if isinstance(error, commands.CommandNotFound):
                return

            logger.error(f"Command error: {error}")
            await ctx.send(f"Error: {error}")

    def add_commands(self):
        """Register all command handlers"""

        # Text commands
        @self.command(name="bgrank", aliases=["rank"])
        async def bgrank_command(ctx, *args):
            await self.process_bgrank(ctx.send, args, game_mode="0")

        @self.command(name="duorank")
        async def duorank_command(ctx, *args):
            await self.process_bgrank(ctx.send, args, game_mode="1")

        @self.command(name="bgdaily", aliases=["daily", "day"])
        async def bgdaily_command(ctx, *args):
            await self.process_bgdaily(ctx.send, args, game_mode="0")

        @self.command(name="duodaily", aliases=["duoday"])
        async def duodaily_command(ctx, *args):
            await self.process_bgdaily(ctx.send, args, game_mode="1")

        @self.command(name="yesterday", aliases=["yday"])
        async def yesterday_command(ctx, *args):
            await self.process_bgyday(ctx.send, args, game_mode="0")

        @self.command(name="duoyesterday", aliases=["duoyday"])
        async def duoyesterday_command(ctx, *args):
            await self.process_bgyday(ctx.send, args, game_mode="1")

        @self.command(name="bgweekly", aliases=["weekly", "week"])
        async def bgweekly_command(ctx, *args):
            await self.process_bgweekly(ctx.send, args, game_mode="0")

        @self.command(name="duoweekly", aliases=["duoweek"])
        async def duoweekly_command(ctx, *args):
            await self.process_bgweekly(ctx.send, args, game_mode="1")

        @self.command(name="peak")
        async def peak_command(ctx, *args):
            await self.process_peak(ctx.send, args, game_mode="0")

        @self.command(name="duopeak")
        async def duopeak_command(ctx, *args):
            await self.process_peak(ctx.send, args, game_mode="1")

        @self.command(name="stats", aliases=["bgstats"])
        async def stats_command(ctx, *args):
            await self.process_stats(ctx.send, args, game_mode="0")

        @self.command(name="duostats")
        async def duostats_command(ctx, *args):
            await self.process_stats(ctx.send, args, game_mode="1")

        @self.command(name="top", aliases=["bgtop"])
        async def top_command(ctx, *args):
            await self.process_top(ctx.send, args, game_mode="0")

        @self.command(name="duotop")
        async def duotop_command(ctx, *args):
            await self.process_top(ctx.send, args, game_mode="1")

        @self.command(name="patch")
        async def patch_command(ctx):
            await ctx.send(self.db.patch_link)

        # Renamed from 'help' to 'commands' to avoid conflict
        @self.command(name="commands", aliases=["cmds", "commandlist"])
        async def commands_command(ctx):
            await ctx.send(
                "Available commands with !:\n"
                "!bgrank <player_name or rank> [region]\n"
                "!daily <player_name or rank> [region]\n"
                "!weekly <player_name or rank> [region]\n"
                "!peak <player_name or rank> [region]\n"
                "!stats [region]\n"
                "!top [region]\n"
                "!patch\n"
                "Add 'duo' prefix for duo mode (e.g., !duorank)"
            )

        # Admin commands for alias and channel management
        @self.command(name="addalias")
        async def addalias_command(ctx, alias=None, player_name=None):
            if not alias or not player_name:
                await ctx.send("Usage: !addalias <alias> <player_name>")
                return

            # Check if user has permission
            if ctx.guild and ctx.guild.id == LII_DISCORD_ID:
                response = self.dynamo_client.add_alias(alias, player_name)
                await ctx.send(response)
            else:
                await ctx.send("You don't have permission to use this command.")

        @self.command(name="deletealias")
        async def deletealias_command(ctx, alias=None):
            if not alias:
                await ctx.send("Usage: !deletealias <alias>")
                return

            # Check if user has permission
            if ctx.guild and ctx.guild.id == LII_DISCORD_ID:
                response = self.dynamo_client.delete_alias(alias)
                await ctx.send(response)
            else:
                await ctx.send("You don't have permission to use this command.")

        @self.command(name="addchannel")
        async def addchannel_command(ctx, channel=None, player_name=None):
            if not channel:
                await ctx.send("Usage: !addchannel <channel> [player_name]")
                return

            # Check if user has permission
            if ctx.guild and ctx.guild.id == LII_DISCORD_ID:
                response = self.dynamo_client.add_channel(channel, player_name)
                await ctx.send(response)
            else:
                await ctx.send("You don't have permission to use this command.")

        @self.command(name="deletechannel")
        async def deletechannel_command(ctx, channel=None):
            if not channel:
                await ctx.send("Usage: !deletechannel <channel>")
                return

            # Check if user has permission
            if ctx.guild and ctx.guild.id == LII_DISCORD_ID:
                response = self.dynamo_client.delete_channel(channel)
                await ctx.send(response)
            else:
                await ctx.send("You don't have permission to use this command.")

    # Command processing methods
    async def process_bgrank(self, responder, args, game_mode="0"):
        """Process bgrank command"""
        try:
            player_name = args[0] if args else None
            region = args[1] if len(args) > 1 else None

            if not player_name:
                await responder("Usage: !rank <player_name or rank> [region]")
                return

            response = self.db.rank(player_name, region, game_mode)
            await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_bgrank: {e}")

    async def process_bgdaily(self, responder, args, game_mode="0"):
        """Process bgdaily command"""
        try:
            player_name = args[0] if args else None
            region = args[1] if len(args) > 1 else None

            if not player_name:
                await responder("Usage: !daily <player_name or rank> [region]")
                return

            response = self.db.day(player_name, region, game_mode)
            await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_bgdaily: {e}")

    async def process_bgyday(self, responder, args, game_mode="0"):
        """Process yesterday command"""
        try:
            player_name = args[0] if args else None
            region = args[1] if len(args) > 1 else None

            if not player_name:
                await responder("Usage: !yesterday <player_name or rank> [region]")
                return

            response = self.db.day(player_name, region, game_mode, offset=1)
            await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_bgyday: {e}")

    async def process_bgweekly(self, responder, args, game_mode="0"):
        """Process weekly command"""
        try:
            player_name = args[0] if args else None
            region = args[1] if len(args) > 1 else None

            if not player_name:
                await responder("Usage: !weekly <player_name or rank> [region]")
                return

            response = self.db.week(player_name, region, game_mode)
            await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_bgweekly: {e}")

    async def process_peak(self, responder, args, game_mode="0"):
        """Process peak command"""
        try:
            player_name = args[0] if args else None
            region = args[1] if len(args) > 1 else None

            if not player_name:
                await responder("Usage: !peak <player_name or rank> [region]")
                return

            response = self.db.peak(player_name, region, game_mode)
            await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_peak: {e}")

    async def process_stats(self, responder, args, game_mode="0"):
        """Process stats command"""
        try:
            server = args[0] if args else None

            response = self.db.region_stats(server, game_mode)
            await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_stats: {e}")

    async def process_top(self, responder, args, game_mode="0"):
        """Process top command"""
        try:
            server = args[0] if args else None

            if server is None or server == "":
                response = self.db.top10(game_mode=game_mode)
                await responder(response)
            else:
                response = self.db.top10(server, game_mode)
                await responder(response)
        except Exception as e:
            await responder("An error occurred while processing the command.")
            logger.error(f"Error in process_top: {e}")


def main():
    """Main function to run the Discord bot"""
    try:
        bot = DiscordBot()
        logger.info("Starting Discord bot...")
        bot.run(os.environ["DISCORD_TOKEN"])
    except Exception as e:
        logger.error(f"Error starting Discord bot: {e}")


if __name__ == "__main__":
    main()
