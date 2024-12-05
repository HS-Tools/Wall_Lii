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
            initial_channels=["liihs", "haitahs", "beterbabbit", "slyders_hs"]
        )
        # Initialize DB connection
        if use_aws:
            # Use AWS DynamoDB
            self.db = LeaderboardDB(table_name='HearthstoneLeaderboardV2')
        else:
            # Use local test DynamoDB
            self.db = LeaderboardDB(
                endpoint_url='http://localhost:8000',
                table_name='HearthstoneLeaderboardTest'  # Use test table
            )

    async def event_ready(self):
        logger.info(f"Bot ready | {self.nick}")

    @commands.command(name="duorank")
    async def duorank(self, ctx, player_or_rank=None, server=None):
        """Same as bgrank but for duo mode"""
        player_or_rank = clean_input(player_or_rank)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name
        
        server = clean_input(server)
        response = self.db.format_player_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="bgrank")
    async def bgrank(self, ctx, player_or_rank=None, server=None):
        """Get player rank, defaulting to channel name if no player specified"""
        # Use channel name as default player if none provided
        player_or_rank = clean_input(player_or_rank)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name

        server = clean_input(server)
        response = self.db.format_player_stats(
            player_or_rank, server, game_mode="0"
        )
        await ctx.send(response)

    @commands.command(name="duodaily")
    async def duodaily(self, ctx, player_or_rank=None, server=None):
        """Same as bgdaily but for duo mode"""
        player_or_rank = clean_input(player_or_rank)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name

        server = clean_input(server)
        response = self.db.format_daily_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="bgdaily")
    async def bgdaily(self, ctx, player_or_rank=None, server=None):
        """Keep existing bgdaily but explicitly set game_mode"""
        player_or_rank = clean_input(player_or_rank)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name

        server = clean_input(server)
        response = self.db.format_daily_stats(
            player_or_rank, server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duopeak")
    async def duopeak(self, ctx, player_or_rank=None, server=None):
        """Same as peak but for duo mode"""
        player_or_rank = clean_input(player_or_rank)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name

        server = clean_input(server)
        response = self.db.format_peak_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="peak")
    async def peak(self, ctx, player_name=None, server=None):
        """Keep existing peak but explicitly set game_mode"""
        player_name = clean_input(player_name)

        if player_name is None or player_name == "":
            player_name = ctx.channel.name

        server = clean_input(server)
        response = self.db.format_peak_stats(
            player_name, server, game_mode="0"
        )  # '0' for regular mode
        await ctx.send(response)

    @commands.command(name="duostats")
    async def duostats(self, ctx, server=None):
        """Same as stats but for duo mode"""
        server = clean_input(server)
        if server is None or server == "":
            # No server specified, get stats for all servers
            servers = ["NA", "EU", "AP"]
            responses = []
            for srv in servers:
                response = self.db.format_region_stats(srv, game_mode="1")
                if "No stats available" not in response:
                    # Omit the maximum MMR part
                    response = response.split(". The highest rating is")[0]
                    responses.append(response)
            await ctx.send(" | ".join(responses))
        else:
            # Server specified, get stats for that server
            server = clean_input(server)
            response = self.db.format_region_stats(server, game_mode="1")
            await ctx.send(response)

    @commands.command(name="stats")
    async def stats(self, ctx, server=None):
        """Display server stats, or all servers if no server specified"""
        server = clean_input(server)
        if server is None or server == "":
            # No server specified, get stats for all servers
            servers = ["NA", "EU", "AP"]
            responses = []
            for srv in servers:
                response = self.db.format_region_stats(srv, game_mode="0")
                if "No stats available" not in response:
                    # Omit the maximum MMR part
                    response = response.split(". The highest rating is")[0]
                    responses.append(response)
            await ctx.send(" | ".join(responses))
        else:
            # Server specified, get stats for that server
            server = clean_input(server)
            response = self.db.format_region_stats(server, game_mode="0")
            await ctx.send(response)

    @commands.command(name="duotop")
    async def duotop(self, ctx, server=None):
        """Same as top but for duo mode"""
        server = clean_input(server)
        if server is None or server == "":
            # No server specified, get top players globally
            players = self.db.get_top_players_global(game_mode="1", limit=10)
            if not players:
                await ctx.send("No players found globally")
                return

            # Format each player as "name (rating) from server"
            formatted = [
                f"{i+1}. {p['PlayerName']}: {p['LatestRating']} ({p['Server']})"
                for i, p in enumerate(players)
            ]

            await ctx.send(f"Top 10 globally: {', '.join(formatted)}")
        else:
            # Server specified, get top players for that server
            server = clean_input(server)
            response = self.db.format_top_players(server, game_mode="1")

            print("Response:", response)
            await ctx.send(response)

    @commands.command(name="bgtop")
    async def bgtop(self, ctx, server=None):
        """Display top players, or top globally if no server specified"""
        server = clean_input(server)
        if server is None or server == "":
            # No server specified, get top players globally
            players = self.db.get_top_players_global(game_mode="0", limit=10)
            if not players:
                await ctx.send("No players found globally")
                return

            # Format each player as "name (rating) from server"
            formatted = [
                f"{i+1}. {p['PlayerName']}: {p['LatestRating']} ({p['Server']})"
                for i, p in enumerate(players)
            ]

            await ctx.send(f"Top 10 globally: {', '.join(formatted)}")
        else:
            # Server specified, get top players for that server
            server = clean_input(server)
            response = self.db.format_top_players(server, game_mode="0")

            print("Response:", response)
            await ctx.send(response)

    @commands.command(name="duoweekly")
    async def duoweekly(self, ctx, player_or_rank=None, server=None):
        """Same as bgweekly but for duo mode"""
        player_or_rank = clean_input(player_or_rank)

        if player_or_rank is None or player_or_rank == "":
            player_or_rank = ctx.channel.name

        server = clean_input(server)
        response = self.db.format_weekly_stats(
            player_or_rank, server, game_mode="1"
        )  # '1' for duo mode
        await ctx.send(response)

    @commands.command(name="bgweekly")
    async def bgweekly(self, ctx, player_name=None, server=None):
        """Keep existing bgweekly but explicitly set game_mode"""
        player_name = clean_input(player_name)

        if player_name is None or player_name == "":
            player_name = ctx.channel.name

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
            "Milestones: !8k through !21k [server]. "
            "Valid servers: NA, EU, AP"
        )
        await ctx.send(help_message)

    @commands.command(name='8k')
    async def eight_k(self, ctx, server=None):
        """Show first player to reach 8000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(8000, server)
        await ctx.send(response)

    @commands.command(name='9k')
    async def nine_k(self, ctx, server=None):
        """Show first player to reach 9000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(9000, server)
        await ctx.send(response)

    @commands.command(name='10k')
    async def ten_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(10000, server)
        await ctx.send(response)

    @commands.command(name='11k')
    async def eleven_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(11000, server)
        await ctx.send(response)

    @commands.command(name='12k')
    async def twelve_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(12000, server)
        await ctx.send(response)

    @commands.command(name='13k')
    async def thirteen_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(13000, server)
        await ctx.send(response)

    @commands.command(name='14k')
    async def fourteen_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(14000, server)
        await ctx.send(response)

    @commands.command(name='15k')
    async def fifteen_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(15000, server)
        await ctx.send(response)

    @commands.command(name='16k')
    async def sixteen_k(self, ctx, server=None):
        server = clean_input(server)
        response = self.db.format_milestone_stats(16000, server)
        await ctx.send(response)

    @commands.command(name='17k')
    async def seventeen_k(self, ctx, server=None):
        """Show first player to reach 17000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(17000, server)
        await ctx.send(response)

    @commands.command(name='18k')
    async def eighteen_k(self, ctx, server=None):
        """Show first player to reach 18000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(18000, server)
        await ctx.send(response)

    @commands.command(name='19k')
    async def nineteen_k(self, ctx, server=None):
        """Show first player to reach 19000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(19000, server)
        await ctx.send(response)

    @commands.command(name='20k')
    async def twenty_k(self, ctx, server=None):
        """Show first player to reach 20000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(20000, server)
        await ctx.send(response)

    @commands.command(name='21k')
    async def twentyone_k(self, ctx, server=None):
        """Show first player to reach 21000 rating"""
        server = clean_input(server)
        response = self.db.format_milestone_stats(21000, server)
        await ctx.send(response)

    @commands.command(name='goodbot')
    async def goodbot(self, ctx):
        """Respond to praise with a robotic acknowledgment"""
        await ctx.send("MrDestructoid Just doing my job MrDestructoid")


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
