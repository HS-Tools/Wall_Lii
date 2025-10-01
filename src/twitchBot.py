import datetime
from logger import setup_logger

logger = setup_logger("TwitchBot")
import psycopg2
import sys
import os
import asyncio
import time
from twitchio.ext import commands
from leaderboard import LeaderboardDB
from managers.channel_manager import ChannelManager
from utils.buddy import get_buddy_text, get_trinket_text, get_buddy_gold_tier_message, update_buddy_dict_and_trinket_dict
from utils.aws_dynamodb import DynamoDBClient
from utils.regions import is_server
from utils.supabase_channels import add_channel, delete_channel, update_player


class TwitchBot(commands.Bot):
    async def event_message(self, message):
        await self.handle_commands(message)

        if message.channel.name == "dogdog" and not message.content.lower().startswith(
            "!patch"
        ):
            words = message.content.lower().split()
            if "patch" in words:
                now = time.time()
                last_trigger = self.last_patch_trigger.get(message.channel.name, 0)
                if now - last_trigger >= 30:
                    await message.channel.send(self.db.patch_link)
                    self.last_patch_trigger[message.channel.name] = now

    priority_channels = (
        {"liihs"}
        if "--test" in sys.argv
        else {
            "liihs",
            "walliibot",
            "jeefhs",
            "beterbabbit",
            "dogdog",
            "rdulive",
            "xqn_thesad",
            "terrytsang",
        }
    )  # These channels are always joined

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
        self.dynamo_client = DynamoDBClient()

        # Track joined channels to avoid duplicate join/leave attempts
        self.currently_joined = set(self.priority_channels)
        self.last_patch_trigger = {}
        # Global dictionary to track posted news: {created_at: {"title": ..., "slug": ..., "first_post_time": datetime, "last_sent": {channel: datetime}}}
        self.posted_news = {}
        self.latest_news_seen = datetime.datetime.now(datetime.timezone.utc)

    async def event_ready(self):
        logger.info(
            f"Logged in as | {self.nick} at {datetime.datetime.now().isoformat()}"
        )
        logger.info(f"Initial channel list: {self.channel_manager.all_channels}")
        # Start the background task to check live channels
        self.bg_task = asyncio.create_task(self.channel_check_loop())
        # Start the news announcer background task
        self.news_task = asyncio.create_task(self.news_announcer())

    async def channel_check_loop(self):
        """Background task to periodically check for live channels"""
        if "--test" in sys.argv:
            logger.info("Running in test mode — skipping channel check loop.")
            return

        while True:
            logger.info(
                f"channel_check_loop iteration start at {datetime.datetime.now().isoformat()}"
            )
            # Refresh the currently_joined set from Twitch's actual connection state
            actual_connected = {
                ch.name for ch in getattr(self, "connected_channels", [])
            }
            logger.debug(f"Fetched connected_channels from library: {actual_connected}")
            self.currently_joined = set(actual_connected)
            try:
                # Get live channels from the channel manager
                live_channels = await self.channel_manager.get_live_channels()

                # Combine with priority channels
                channels_to_join = live_channels.union(self.priority_channels)

                # Determine which channels to join and leave
                to_join = channels_to_join - self.currently_joined
                to_leave = self.currently_joined - channels_to_join

                # Join new channels
                if to_join:
                    logger.info(
                        f"Attempting to join {len(to_join)} channels: {', '.join(to_join)}"
                    )
                    for channel in to_join:
                        try:
                            # Join channels one by one to better handle errors
                            await self.join_channels([channel])
                            # self.currently_joined.add(channel)  # Now handled by refresh at top of loop
                            # Small delay to avoid rate limits
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Error joining {channel}: {e}")
                    # Debug/log: Currently joined after join
                    logger.debug(
                        f"Currently joined after join: {self.currently_joined}"
                    )
                    # Verify actual Twitch connection state against internal state
                    actual_connected = {
                        ch.name for ch in getattr(self, "connected_channels", [])
                    }
                    missing_joins = to_join - actual_connected
                    if missing_joins:
                        logger.warning(
                            f"Channels reported joined but not in Twitch connection list: {', '.join(missing_joins)}"
                        )

                # Leave channels that are no longer live (except priority channels)
                if to_leave:
                    to_leave_non_priority = to_leave - self.priority_channels
                    if to_leave_non_priority:
                        logger.info(
                            f"Leaving {len(to_leave_non_priority)} channels: {', '.join(to_leave_non_priority)}"
                        )
                        for channel in to_leave_non_priority:
                            try:
                                await self.part_channels([channel])
                                # self.currently_joined.remove(channel)  # Now handled by refresh at top of loop
                                logger.info(f"Left channel: {channel}")
                                # Small delay to avoid rate limits
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logger.error(f"Error leaving {channel}: {e}")

            except Exception as e:
                logger.exception("Error in channel check loop")

            # Check every minute
            await asyncio.sleep(60)

    async def event_join(self, channel, user):
        """Log when the bot has successfully joined a channel."""
        if user.name.lower() == self.nick.lower():
            logger.info(
                f"Confirmed bot joined channel: {channel.name} at {datetime.datetime.now().isoformat()}"
            )

    async def event_part(self, channel, user):
        """Log when the bot has successfully left a channel."""
        if user.name.lower() == self.nick.lower():
            logger.info(
                f"Confirmed bot left channel: {channel.name} at {datetime.datetime.now().isoformat()}"
            )

    # --- News Announcer Background Task ---

    async def news_announcer(self):
        """
        Background task to announce latest news to live Hearthstone channels every 60 seconds.
        Only posts to each channel if last message for the post was >2h ago and within 24h of first announcement.
        Only processes news posts that are battlegrounds_relevant = True.
        """
        await asyncio.sleep(5)  # Wait for bot to be ready
        # Prepare DB connection parameters from environment
        PG_HOST = os.environ.get("DB_HOST")
        PG_PORT = int(os.environ.get("DB_PORT", "5432"))
        PG_NAME = os.environ.get("DB_NAME")
        PG_USER = os.environ.get("DB_USER")
        PG_PASSWORD = os.environ.get("DB_PASSWORD")
        conn = None
        while True:
            try:
                # Connect to the DB if not already connected
                if conn is None or conn.closed:
                    conn = psycopg2.connect(
                        host=PG_HOST,
                        port=PG_PORT,
                        dbname=PG_NAME,
                        user=PG_USER,
                        password=PG_PASSWORD,
                    )
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT title, slug, created_at FROM news_posts WHERE battlegrounds_relevant = True ORDER BY created_at DESC LIMIT 1"
                    )
                    row = cur.fetchone()
                    if not row:
                        await asyncio.sleep(60)
                        continue
                    title, slug, created_at = row
                    # Parse created_at to UTC datetime
                    if isinstance(created_at, str):
                        created_at = datetime.datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                    elif not isinstance(created_at, datetime.datetime):
                        created_at = datetime.datetime.utcfromtimestamp(created_at)
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                    # Use ISO string as unique key
                    key = created_at.isoformat()
                    now = datetime.datetime.now(datetime.timezone.utc)
                    # Only proceed if this news post is newer than the latest we've seen
                    if created_at <= self.latest_news_seen:
                        await asyncio.sleep(60)
                        continue

                    # New post detection
                    if created_at > self.latest_news_seen:
                        print("New battlegrounds-relevant post found")
                        self.latest_news_seen = created_at
                        # Initialize tracking for this post
                        self.posted_news[key] = {
                            "title": title,
                            "slug": slug,
                            "first_post_time": now,
                            "last_sent": {},  # channel: datetime
                        }
                        # Clean up old posts (>36h old)
                        for k in list(self.posted_news.keys()):
                            if (
                                now - self.posted_news[k]["first_post_time"]
                            ).total_seconds() > 36 * 3600:
                                self.posted_news.pop(k)

                    # Prepare per-post messages and send to live hearthstone channels every 2h until 24h elapse
                    # Build the message once per post
                    for k, post in self.posted_news.items():
                        # Check for new buddies and trinkets:
                        update_buddy_dict_and_trinket_dict()
                        
                        first_post = post["first_post_time"]
                        # Skip if more than 24h since first post
                        if (now - first_post).total_seconds() > 24 * 3600:
                            continue
                        msg = f"BGs update: {post['title']} — https://wallii.gg/news/{post['slug']}"
                        # Determine channels to send
                        for channel in self.channel_manager.hearthstone_channels:
                            last = post["last_sent"].get(channel)
                            # Send if never sent or more than 2h since last send
                            if last is None or (now - last).total_seconds() >= 2 * 3600:
                                # Find Channel object
                                ch_obj = next(
                                    (
                                        ch
                                        for ch in getattr(
                                            self, "connected_channels", []
                                        )
                                        if hasattr(ch, "name") and ch.name == channel
                                    ),
                                    None,
                                )
                                if ch_obj:
                                    try:
                                        await ch_obj.send(msg)
                                        post["last_sent"][channel] = now
                                    except Exception as e:
                                        print(f"Error sending news to {channel}: {e}")
            except Exception as exc:
                print(f"Error in news_announcer: {exc}")
                # If DB error, close and reconnect next time
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None
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

    def process_args(self, arg1, arg2, channel_name):
        arg1 = self.clean_input(arg1)
        if is_server(arg1) and not arg2:
            return arg1, channel_name
        if not arg1:
            return channel_name, None
        return arg1, arg2

    @commands.command(name="rank", aliases=["bgrank", "duorank"])
    async def rank_command(self, ctx, arg1=None, arg2=None):
        """Get player rank, defaulting to channel name if no player specified"""
        arg1, arg2 = self.process_args(arg1, arg2, ctx.channel.name)
        game_mode = "1" if self.get_command_name(ctx) == "duorank" else "0"
        response = self.db.rank(
            self.clean_input(arg1), self.clean_input(arg2), game_mode
        )
        await ctx.send(response)

    @commands.command(name="day", aliases=["bgdaily", "daily", "duoday", "duodaily"])
    async def day_command(self, ctx, arg1=None, arg2=None):
        """Get player's daily stats"""
        arg1, arg2 = self.process_args(arg1, arg2, ctx.channel.name)
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
        arg1, arg2 = self.process_args(arg1, arg2, ctx.channel.name)
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
        arg1, arg2 = self.process_args(arg1, arg2, ctx.channel.name)
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
        arg1, arg2 = self.process_args(arg1, arg2, ctx.channel.name)
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
        arg1, arg2 = self.process_args(arg1, arg2, ctx.channel.name)
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

    @commands.command(name="buddy")
    async def buddy(self, ctx):
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            return
        result = get_buddy_text(args[1])
        if result:
            await ctx.send(result[1])

    @commands.command(name="goldenbuddy")
    async def goldenbuddy(self, ctx):
        if ctx.channel.name == "dogdog":
            return
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            return
        result = get_buddy_text(args[1])
        if result:
            await ctx.send(result[2])

    @commands.command(name="trinket")
    async def trinket(self, ctx):
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            return
        result = get_trinket_text(" ".join(args[1:]))
        if result:
            await ctx.send(result)

    @commands.command(name="buddygold")
    async def buddygold(self, ctx):
        args = ctx.message.content.split(" ")
        if len(args) < 2:
            await ctx.send("Add a tier between 1 and 6 like !buddygold 3")
            return
        message = get_buddy_gold_tier_message(args[1])
        await ctx.send(message)

    @commands.command(name="patch")
    async def patch_command(self, ctx):
        """Get the current patch link"""
        response = self.db.patch_link
        await ctx.send(response)

    @commands.command(name="addchannel")
    async def addchannel_command(self, ctx, player_name=None):
        """Add the current channel to the channel list with optional player name"""
        if ctx.channel.name != "walliibot":
            return
        username = ctx.author.name.lower()
        if not player_name:
            player_name = username
        response = add_channel(username, player_name)
        await ctx.send(response)

    @commands.command(name="addname")
    async def addname_command(self, ctx, player_name=None):
        """Add an alias for the current channel name"""
        if ctx.channel.name != "walliibot":
            return

        if not player_name:
            await ctx.send("Usage: !addname <player_name>")
            return

        username = ctx.author.name.lower()
        response = self.dynamo_client.add_alias(username, player_name)
        response = update_player(username, player_name)
        await ctx.send(response)

    @commands.command(name="deletechannel")
    async def deletechannel_command(self, ctx):
        """Delete the current channel from the channel list"""
        if ctx.channel.name != "walliibot":
            return
        username = ctx.author.name.lower()
        response = delete_channel(username)
        await ctx.send(response)

    @commands.command(name="help", aliases=["commands", "wall_lii"])
    async def help_command(self, ctx, command_name=None):
        """Display help info"""
        await ctx.send(
            "Use !rank, !day, !week, !top, !patch + more — day resets on 00:00 PST, week resets on Mon. More info: wallii.gg/help"
        )

    @commands.command(name="goodbot")
    async def goodbot(self, ctx):
        """Respond to praise with a robotic acknowledgment"""
        await ctx.send("MrDestructoid Just doing my job MrDestructoid")

    @commands.command(name="bgdailii")
    async def bgdailii(self, ctx):
        """Respond to criticism with a robotic acknowledgment"""
        await ctx.send(self.db.day("lii", None, "0"))


def main():
    bot = TwitchBot()
    bot.run()


if __name__ == "__main__":
    main()
