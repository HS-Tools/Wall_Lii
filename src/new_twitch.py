import os
from twitchio.ext import commands
from leaderboard import LeaderboardDB

class TwitchBot(commands.Bot):
  def __init__(self):
    # Initialize the bot with the necessary credentials
    super().__init__(
        token=os.environ['TMI_TOKEN'],
        prefix=os.environ.get('BOT_PREFIX', '!'),
        initial_channels=['liihs']
    )
    self.db = LeaderboardDB()

  async def event_ready(self):
    print(f'Logged in as | {self.nick}')

  def clean_input(self, user_input):
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
  
  def get_command_name(self, ctx):
    return ctx.message.content.split()[0].lstrip('!')

  @commands.command(name='rank', aliases=["bgrank", "duorank"])
  async def rank_command(self, ctx, arg1=None, arg2=None):
    """Get player rank, defaulting to channel name if no player specified"""
    arg1 = arg1 or ctx.channel.name
    game_mode = "1" if self.get_command_name(ctx) == "duorank" else "0"
    response = self.db.rank(self.clean_input(arg1), self.clean_input(arg2), game_mode)
    await ctx.send(response)

  @commands.command(name='day', aliases=["bgdaily", "daily", "duoday", "duodaily"])
  async def day_command(self, ctx, arg1=None, arg2=None):
    """Get player's daily stats"""
    arg1 = arg1 or ctx.channel.name
    game_mode = "1" if self.get_command_name(ctx) == "duodaily" or self.get_command_name(ctx) == "duoday" else "0"
    response = self.db.day(self.clean_input(arg1), self.clean_input(arg2), game_mode)
    await ctx.send(response)

  @commands.command(name="yesterday", aliases=["bgyesterday", "duoyesterday", "yday", "duoyday"])
  async def yesterday_command(self, ctx, arg1=None, arg2=None):
    """Get player's stats for yesterday for both regular and duo modes"""
    arg1 = arg1 or ctx.channel.name
    game_mode = "1" if self.get_command_name(ctx) == "duoyesterday" or self.get_command_name(ctx) == "duoyday" else "0"
    response = self.db.day(self.clean_input(arg1), self.clean_input(arg2), game_mode, offset=1)
    await ctx.send(response)

  @commands.command(name='peak', aliases=["duopeak"])
  async def peak_command(self, ctx, arg1=None, arg2=None):
    """Get player's peak rating this season"""
    game_mode = "1" if self.get_command_name(ctx) == "duopeak" else "0"
    response = self.db.peak(self.clean_input(arg1), self.clean_input(arg2), game_mode)
    await ctx.send(response)

  @commands.command(name='week', aliases=["bgweek", "bgweekly", "duoweek", "duoweekly"])
  async def week_command(self, ctx, arg1=None, arg2=None):
    """Get player's weekly stats"""
    game_mode = "1" if self.get_command_name(ctx) == "duoweek" or self.get_command_name(ctx) == "duoweekly" else "0"
    response = self.db.week(self.clean_input(arg1), self.clean_input(arg2), game_mode)
    await ctx.send(response)

  @commands.command(name="lastweek", aliases=["bglastweek", "duolastweek", "lweek", "duolweek"])
  async def lastweek_command(self, ctx, arg1=None, arg2=None):
    """Get player's stats for last week for both regular and duo modes"""
    game_mode = "1" if self.get_command_name(ctx) == "duolastweek" or self.get_command_name(ctx) == "duolweek" else "0"
    response = self.db.week(self.clean_input(arg1), self.clean_input(arg2), game_mode, offset=1)
    await ctx.send(response)

  @commands.command(name='top', aliases=["bgtop", "duotop"])
  async def top_command(self, ctx, region=None, game_mode="0"):
    """Get top 10 players for a region or globally"""
    game_mode = "1" if self.get_command_name(ctx) == "duotop" else "0"
    response = self.db.top10(self.clean_input(region), game_mode)
    await ctx.send(response)

  @commands.command(name='stats', aliases=["bgstats", "duostats"])
  async def stats_command(self, ctx, region=None, game_mode="0"):
    """Get region stats"""
    game_mode = "1" if self.get_command_name(ctx) == "duostats" else "0"
    response = self.db.region_stats(self.clean_input(region), game_mode)
    await ctx.send(response)

  @commands.command(name='milestone')
  async def milestone_command(self, ctx, milestone=None, region=None):
    """Get milestone information"""
    if not milestone:
      await ctx.send("Please specify a milestone (e.g., !milestone 13k)")
      return
    response = self.db.milestone(self.clean_input(milestone), self.clean_input(region))
    await ctx.send(response)

  @commands.command(name='patch')
  async def patch_command(self, ctx):
    """Get the current patch link"""
    response = self.db.patch_link
    await ctx.send(response)

def main():
  bot = TwitchBot()
  bot.run()

if __name__ == "__main__":
  main()