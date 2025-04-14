import os
import asyncio
from twitchio.ext import commands
from leaderboard import LeaderboardDB
from managers.channel_manager import ChannelManager


class TwitchBot(commands.Bot):
    priority_channels = {
        "liihs",
        "jeefhs",
        "beterbabbit",
        "dogdog",
        "rdulive",
        "xqn_thesad",
        "superjj102",
        "terrytsang",
    }  # These channels are always joined

    def __init__(self):
        # Initialize the bot with the necessary credentials
        super().__init__(
            token=os.environ["TMI_TOKEN"],
            prefix=os.environ.get("BOT_PREFIX", "!"),
            initial_channels=list(self.priority_channels),
        )
        self.channel_manager = ChannelManager(self.priority_channels)
        self.db = LeaderboardDB()
        self.bg_task = None

        # Track joined channels to avoid duplicate join/leave attempts
        self.currently_joined = set(self.priority_channels)

    async def event_ready(self):
        print(f"Logged in as | {self.nick}")
        # Start the background task to check live channels
        self.bg_task = asyncio.create_task(self.channel_check_loop())

    async def channel_check_loop(self):
        """Background task to periodically check for live channels"""
        while True:
            try:
                # Get live channels from the channel manager
                live_channels = await self.channel_manager.get_live_channels(
                    self.channel_manager.all_channels
                )

                # Combine with priority channels
                channels_to_join = live_channels.union(self.priority_channels)

                # Determine which channels to join and leave
                to_join = channels_to_join - self.currently_joined
                to_leave = self.currently_joined - channels_to_join

                # Join new channels
                if to_join:
                    print(
                        f"Attempting to join {len(to_join)} channels: {', '.join(to_join)}"
                    )
                    for channel in to_join:
                        try:
                            # Join channels one by one to better handle errors
                            await self.join_channels([channel])
                            self.currently_joined.add(channel)
                            print(f"Successfully joined channel: {channel}")
                            # Small delay to avoid rate limits
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"Error joining {channel}: {e}")

                # Leave channels that are no longer live (except priority channels)
                if to_leave:
                    to_leave_non_priority = to_leave - self.priority_channels
                    if to_leave_non_priority:
                        print(
                            f"Leaving {len(to_leave_non_priority)} channels: {', '.join(to_leave_non_priority)}"
                        )
                        for channel in to_leave_non_priority:
                            try:
                                await self.part_channels([channel])
                                self.currently_joined.remove(channel)
                                print(f"Left channel: {channel}")
                                # Small delay to avoid rate limits
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                print(f"Error leaving {channel}: {e}")

            except Exception as e:
                print(f"Error in channel check loop: {e}")

            # Check every minute
            await asyncio.sleep(60)

    def clean_input(self, user_input):
        """Cleans user input to remove any unwanted characters or prefixes."""
        # Remove invisible characters and leading/trailing whitespace
        if not user_input:
            return None
        cleaned = "".join(c for c in user_input if c.isprintable()).strip()

        # Remove leading '!' to prevent commands
        if cleaned.startswith("!"):
            cleaned = cleaned.lstrip("!")  # Removes all leading '!' characters

        return cleaned

    def get_command_name(self, ctx):
        return ctx.message.content.split()[0].lstrip("!")

    @commands.command(name="rank", aliases=["bgrank", "duorank"])
    async def rank_command(self, ctx, arg1=None, arg2=None):
        """Get player rank, defaulting to channel name if no player specified"""
        arg1 = self.clean_input(arg1) or ctx.channel.name
        game_mode = "1" if self.get_command_name(ctx) == "duorank" else "0"
        response = self.db.rank(
            self.clean_input(arg1), self.clean_input(arg2), game_mode
        )
        await ctx.send(response)

    @commands.command(name="day", aliases=["bgdaily", "daily", "duoday", "duodaily"])
    async def day_command(self, ctx, arg1=None, arg2=None):
        """Get player's daily stats"""
        arg1 = self.clean_input(arg1) or ctx.channel.name
        game_mode = (
            "1"
            if self.get_command_name(ctx) == "duodaily"
            or self.get_command_name(ctx) == "duoday"
            else "0"
        )
        response = self.db.day(
            self.clean_input(arg1), self.clean_input(arg2), game_mode
        )
        await ctx.send(response)

    @commands.command(
        name="yesterday", aliases=["bgyesterday", "duoyesterday", "yday", "duoyday"]
    )
    async def yesterday_command(self, ctx, arg1=None, arg2=None):
        """Get player's stats for yesterday for both regular and duo modes"""
        arg1 = self.clean_input(arg1) or ctx.channel.name
        game_mode = (
            "1"
            if self.get_command_name(ctx) == "duoyesterday"
            or self.get_command_name(ctx) == "duoyday"
            else "0"
        )
        response = self.db.day(
            self.clean_input(arg1), self.clean_input(arg2), game_mode, offset=1
        )
        await ctx.send(response)

    @commands.command(name="peak", aliases=["duopeak"])
    async def peak_command(self, ctx, arg1=None, arg2=None):
        """Get player's peak rating this season"""
        arg1 = self.clean_input(arg1) or ctx.channel.name
        game_mode = "1" if self.get_command_name(ctx) == "duopeak" else "0"
        response = self.db.peak(
            self.clean_input(arg1), self.clean_input(arg2), game_mode
        )
        await ctx.send(response)

    @commands.command(
        name="week", aliases=["bgweek", "bgweekly", "duoweek", "duoweekly"]
    )
    async def week_command(self, ctx, arg1=None, arg2=None):
        """Get player's weekly stats"""
        arg1 = self.clean_input(arg1) or ctx.channel.name
        game_mode = (
            "1"
            if self.get_command_name(ctx) == "duoweek"
            or self.get_command_name(ctx) == "duoweekly"
            else "0"
        )
        response = self.db.week(
            self.clean_input(arg1), self.clean_input(arg2), game_mode
        )
        await ctx.send(response)

    @commands.command(
        name="lastweek", aliases=["bglastweek", "duolastweek", "lweek", "duolweek"]
    )
    async def lastweek_command(self, ctx, arg1=None, arg2=None):
        """Get player's stats for last week for both regular and duo modes"""
        arg1 = self.clean_input(arg1) or ctx.channel.name
        game_mode = (
            "1"
            if self.get_command_name(ctx) == "duolastweek"
            or self.get_command_name(ctx) == "duolweek"
            else "0"
        )
        response = self.db.week(
            self.clean_input(arg1), self.clean_input(arg2), game_mode, offset=1
        )
        await ctx.send(response)

    @commands.command(name="top", aliases=["bgtop", "duotop"])
    async def top_command(self, ctx, region=None):
        """Get top 10 players for a region or globally"""
        game_mode = "1" if self.get_command_name(ctx) == "duotop" else "0"
        response = self.db.top10(self.clean_input(region), game_mode)
        await ctx.send(response)

    @commands.command(name="stats", aliases=["bgstats", "duostats"])
    async def stats_command(self, ctx, region=None, game_mode="0"):
        """Get region stats"""
        game_mode = "1" if self.get_command_name(ctx) == "duostats" else "0"
        response = self.db.region_stats(self.clean_input(region), game_mode)
        await ctx.send(response)

    @commands.command(name="milestone")
    async def milestone_command(self, ctx, milestone=None, region=None):
        """Get milestone information"""
        if not milestone:
            await ctx.send("Please specify a milestone (e.g., !milestone 13k)")
            return
        response = self.db.milestone(
            self.clean_input(milestone), self.clean_input(region)
        )
        await ctx.send(response)

    @commands.command(name="patch")
    async def patch_command(self, ctx):
        """Get the current patch link"""
        response = self.db.patch_link
        await ctx.send(response)

    @commands.command(name="goodbot")
    async def goodbot(self, ctx):
        """Respond to praise with a robotic acknowledgment"""
        await ctx.send("MrDestructoid Just doing my job MrDestructoid")


def main():
    bot = TwitchBot()
    bot.run()


if __name__ == "__main__":
    main()
