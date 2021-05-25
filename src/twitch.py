import os
import threading
import aiocron
from twitchio.ext import commands
from leaderboardBot import LeaderBoardBot
from parseRegion import parseRegion, isRegion
from dotenv import load_dotenv

load_dotenv()

leaderboardBot = LeaderBoardBot()

# Initial setup
channels = leaderboardBot.getChannels()
leaderboardBot.updateAlias()

twitchBot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=channels.keys()
)

if __name__ == '__main__':

    @aiocron.crontab('0 * * * *') ## Every hour on the hour check and update channels
    async def updateChannels():
        all_channels = leaderboardBot.getChannels()
        new_channels = []
        for channel in all_channels.keys():
            if channel not in channels:
                channels[channel] = all_channels[channels]
                new_channels.append(channel)
        await twitchBot.join_channels(new_channels)

    @aiocron.crontab('5 * * * *') ## Every hour on the 5 check and update the alias table
    def updateAlias():
        leaderboardbot.updateAlias()

    twitchThread = threading.Thread(target=twitchBot.run)
    twitchThread.setDaemon(True)
    twitchThread.start()

    while True:
        pass


def parseArgs(ctx):
    default = channels[ctx.channel.name]
    args = ctx.content.split(' ')[1:]
    return leaderboardBot.parseArgs(default, *args)

async def call(ctx, func, name, *args):
    response = func(*args)
    if len(args) >= 2:
        if not isRegion(args[1]):
            response = "Invalid region provided.\n" + response

    await ctx.send(response)

@twitchBot.event
async def event_message(ctx):
    # make sure the bot ignores itself and the streamer
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
        return
    await twitchBot.handle_commands(ctx)

@twitchBot.command(name='bgrank')
async def getRank(ctx):
    if ctx.channel.name == 'ixxdeee':
        return
    args = parseArgs(ctx)
    await call(ctx, leaderboardBot.getRankText, 'rank', *args)

@twitchBot.command(name='bgdaily')
async def getDailyStats(ctx):
    args = parseArgs(ctx)
    await call(ctx, leaderboardBot.getDailyStatsText, 'daily', *args)

@twitchBot.command(name='yesterday')
async def getYesterdayStats(ctx):
    args = parseArgs(ctx)
    args.append(True)   ## send the yesterday value to the function
    await call(ctx, leaderboardBot.getDailyStatsText, 'yesterday', *args)

@twitchBot.command(name='goodbot')
async def goodBot(ctx):
    await ctx.send('MrDestructoid Just doing my job MrDestructoid')

@twitchBot.command(name='wall_lii')
async def wall_lii(ctx):
    await ctx.send('HeyGuys I\'m a bot that checks the BG leaderboard to get data about player ranks and daily MMR fluctuations. I reset daily at Midnight CA time. Try using !bgrank [name] and !bgdaily [name] and !yesterday [name].')

@twitchBot.command(name='help')
async def help(ctx):
    await ctx.send('HeyGuys I\'m a bot that checks the BG leaderboard to get data about player ranks and daily MMR fluctuations. I reset daily at Midnight CA time. Try using !bgrank [name] and !bgdaily [name] and !yesterday [name].')
