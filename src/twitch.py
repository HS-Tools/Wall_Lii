import os
import aiocron
from twitchio.ext import commands
from leaderboardBot import LeaderBoardBot
from parseRegion import isRegion
from dotenv import load_dotenv

load_dotenv()

leaderboardBot = LeaderBoardBot()

initialChannels = leaderboardBot.getChannels()

twitchBot = commands.Bot(
    token=os.environ['TMI_TOKEN'],
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=['liihs']
)

def parseArgs(ctx):
    default = initialChannels[ctx.channel.name]
    args = ctx.content.split(' ')[1:]
    return leaderboardBot.parseArgs(default, *args)

async def call(ctx, func, name, *args):
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!'")
        return

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

@twitchBot.command(name='tomorrow')
async def tomorrow(ctx):
    args = parseArgs(ctx)
    name = args[0]

    if args[0][0] == "!":
        await ctx.send("Names can't start with '!'")
        return

    await ctx.send(f"{name} will be rank 1 for sure liiYep")

@twitchBot.command(name='yesterday')
async def getYesterdayStats(ctx):
    args = parseArgs(ctx)
    args.append(True)   ## send the yesterday value to the function
    await call(ctx, leaderboardBot.getDailyStatsText, 'yesterday', *args)

@twitchBot.command(name='bgdailii')
async def bgdailii(ctx):
    await call(ctx, leaderboardBot.getDailyStatsText, 'daily', 'lii')

@twitchBot.command(name='goodbot')
async def goodBot(ctx):
    await ctx.send('MrDestructoid Just doing my job MrDestructoid')

@twitchBot.command(name='wall_lii')
async def wall_lii(ctx):
    await ctx.send('HeyGuys I\'m a bot that checks the BG leaderboard to get data about player ranks and daily MMR fluctuations. I reset daily at Midnight CA time. Try using !bgrank [name] and !bgdaily [name] and !yesterday [name].')

@twitchBot.command(name='help')
async def help(ctx):
    await ctx.send('HeyGuys I\'m a bot that checks the BG leaderboard to get data about player ranks and daily MMR fluctuations. I reset daily at Midnight CA time. Try using !bgrank [name] and !bgdaily [name] and !yesterday [name].')

if __name__ == '__main__':

    @aiocron.crontab('* * * * *') ## Every minute check for new channels
    async def updateChannels():
        global initialChannels

        channels = leaderboardBot.getChannels()

        joined_channels = list(twitchBot._ws._channel_cache)

        new_channels = []
        greeting_channels = []

        for channel in channels:
            if channel not in joined_channels:
                new_channels.append(channel)

                if channel not in initialChannels:
                    greeting_channels.append(channel)
                    initialChannels = leaderboardBot.getChannels()

            if len(new_channels) >= 10:
                break
        
        print(new_channels)
        await twitchBot.join_channels(new_channels)

        for channel_name in greeting_channels:
            channel = twitchBot.get_channel(channel_name)
            await channel.send(f"Hello @{channel_name} and @chat, I'm a bot that allows you to see leaderboard data for Hearthstone Battlegrounds. Type !help to see all my commands!")

    @aiocron.crontab('* * * * *') ## Every minute check for new alias
    async def updateAlias():
        leaderboardBot.getNewAlias()

    twitchBot.run()
