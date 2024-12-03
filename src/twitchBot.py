import argparse
import os

from dotenv import load_dotenv
from twitchio.ext import commands

from leaderboard_queries import LeaderboardDB
from logger import setup_logger

logger = setup_logger("twitchBot")

# Load environment variables
load_dotenv()


def clean_input(text):
    """Clean input text by removing invisible characters and extra whitespace"""
    if not text:
        return None
    return "".join(c for c in text if c.isprintable()).strip()


class LeaderboardBot(commands.Bot):
    def __init__(self, token, prefix, initial_channels, use_aws=False):
        # Initialize bot with environment variables
        super().__init__(
            token=token,
            irc_token=token,
            client_id=os.environ["CLIENT_ID"],
            nick=os.environ["BOT_NICK"],
            prefix=prefix,
            initial_channels=["liihs", "haitahs"],
        )
        # Initialize DB connection
        if use_aws:
            # Use AWS DynamoDB
            self.db = LeaderboardDB(table_name="HearthstoneLeaderboardV2")
        else:
            # Use local DynamoDB
            self.db = LeaderboardDB(endpoint_url="http://localhost:8000")

    async def event_ready(self):
        logger.info(f"Bot ready | {self.nick}")

    @commands.command(name="duorank")
    async def duorank(self, ctx, player_or_rank, server=None):
        """Same as bgrank but for duo mode"""
        player_or_rank = clean_input(player_or_rank)
        server = clean_input(server)
        response = self.db.format_player_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="bgrank")
    async def bgrank(self, ctx, player_or_rank, server=None):
        """Keep existing bgrank but explicitly set game_mode"""
        player_or_rank = clean_input(player_or_rank)
        server = clean_input(server)
        response = self.db.format_player_stats(
            player_or_rank, server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duodaily")
    async def duodaily(self, ctx, player_or_rank, server=None):
        """Same as bgdaily but for duo mode"""
        player_or_rank = clean_input(player_or_rank)
        server = clean_input(server)
        response = self.db.format_daily_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="bgdaily")
    async def bgdaily(self, ctx, player_or_rank, server=None):
        """Keep existing bgdaily but explicitly set game_mode"""
        player_or_rank = clean_input(player_or_rank)
        server = clean_input(server)
        response = self.db.format_daily_stats(
            player_or_rank, server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duopeak")
    async def duopeak(self, ctx, player_or_rank, server=None):
        """Same as peak but for duo mode"""
        player_or_rank = clean_input(player_or_rank)
        server = clean_input(server)
        response = self.db.format_peak_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="peak")
    async def peak(self, ctx, player_name, server=None):
        """Keep existing peak but explicitly set game_mode"""
        player_name = clean_input(player_name)
        server = clean_input(server)
        response = self.db.format_peak_stats(
            player_name, server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duostats")
    async def duostats(self, ctx, server):
        """Same as stats but for duo mode"""
        server = clean_input(server)
        response = self.db.format_region_stats(
            server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="stats")
    async def stats(self, ctx, server):
        """Keep existing stats but explicitly set game_mode"""
        server = clean_input(server)
        response = self.db.format_region_stats(
            server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duotop")
    async def duotop(self, ctx, server):
        """Same as top but for duo mode"""
        server = clean_input(server)
        response = self.db.format_top_players(server, game_mode="1")  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="top")
    async def top(self, ctx, server):
        """Keep existing top but explicitly set game_mode"""
        server = clean_input(server)
        response = self.db.format_top_players(
            server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duoweekly")
    async def duoweekly(self, ctx, player_or_rank, server=None):
        """Same as bgweekly but for duo mode"""
        player_or_rank = clean_input(player_or_rank)
        server = clean_input(server)
        response = self.db.format_weekly_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="bgweekly")
    async def bgweekly(self, ctx, player_name, server=None):
        """Keep existing bgweekly but explicitly set game_mode"""
        player_name = clean_input(player_name)
        server = clean_input(server)
        response = self.db.format_weekly_stats(
            player_name, server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="help")
    async def help(self, ctx):
        """Display all available commands"""
        help_message = (
            "Commands (regular/duo): "
            "!bgrank/!duorank, "
            "!bgdaily/!duodaily, "
            "!bgweekly/!duoweekly, "
            "!peak/!duopeak, "
            "!stats/!duostats, "
            "!top/!duotop. "
            "Valid servers: NA, EU, AP"
        )
        await ctx.send(help_message)


def main():
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
        token=token, prefix=prefix, initial_channels=channels, use_aws=args.aws
    )
    bot.run()


if __name__ == "__main__":
    main()
