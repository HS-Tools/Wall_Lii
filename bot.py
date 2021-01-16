from twitchio.ext import commands
import os

bot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=[os.environ['CHANNEL']]
)

@bot.event
async def event_ready():
    ws = bot._ws
    await ws.send_privmsg(os.environ['CHANNEL'], "hi this is bot")

@bot.command(name='bgrank')
async def test(ctx):
    await ctx.send('test passed!')

bot.run()