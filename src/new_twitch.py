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

  @commands.command(name='rank')
  async def rank_command(self, ctx, arg1=None, arg2=None):
    """Get player rank, defaulting to channel name if no player specified"""
    arg1 = arg1 or ctx.channel.name
    response = self.db.rank(self.clean_input(arg1), self.clean_input(arg2))
    await ctx.send(response)

  @commands.command(name='day')
  async def day_command(self, ctx, arg1=None, arg2=None):
    """Get player's daily stats"""
    arg1 = arg1 or ctx.channel.name
    response = self.db.day(self.clean_input(arg1), self.clean_input(arg2))
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