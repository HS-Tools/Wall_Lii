import os
import threading
from twitchio.ext import commands
from leaderboardBot import LeaderBoardBot
from parseRegion import parseRegion

channels = {'iamtehshadow': 'tehshadow', 
'dominickstarcraft': 'Dom2805',
'rolferolferolfe': 'rolfe',
'jeeeeeeef': 'jeef',
'xixo': 'xixo',
'terry_tsang_gaming': 'terrytsang',
'cursed_hs': 'cursed',
'awedragon': 'awedragon',
'socktastic': 'socktastic',
'logicandanger': 'logicdanger',
'liihs': 'lii',
'sunglitters': 'sunglitters',
'sevel07': 'sevel',
'endozoa': 'endozoa',
'l0rinda': 'l0rinda',
'sassyrutabaga1': 'rutabaga',
'tylerootd': 'tyler',
'hapabear': 'hapabear',
'ninaisnoob': 'ninaisnoob',
'pockyplays': 'pocky',
'blirby': 'blirby',
'mrincrediblehs': 'mrincredible',
'vendettahsb': 'vendetta',
'jkirek_': 'jkirek',
'deathitselfhs': 'deathitself',
'livvylive': 'livvy',
'duhbbleyou': 'theletterw',
'bofur_hs': 'bofur'}

twitchBot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=channels.keys()
)

@twitchBot.event
async def event_message(ctx):
    # make sure the bot ignores itself and the streamer
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
        return
    await twitchBot.handle_commands(ctx)

@twitchBot.command(name='bgrank')
async def getRank(ctx):
    if len(ctx.content.split(' ')) > 1:
        args = ctx.content.split(' ')[1:3]
    else:
        args = [channels[ctx.channel.name]]

    response = leaderboardBot.getRankText(*args)

    # Add error message if region was invalid
    if len(args) == 2:
        region = args[1]
        if parseRegion(region) is None:
            response = f"Invalid region '{region}'.      " + response

    await ctx.send(response)

@twitchBot.command(name='bgdaily')
async def getDailyStats(ctx):
    if len(ctx.content.split(' ')) > 1:
        tag = ctx.content.split(' ')[1]

        response = leaderboardBot.getDailyStatsText(tag)

        await ctx.send(response)
    else:
        response = leaderboardBot.getDailyStatsText(channels[ctx.channel.name])

        await ctx.send(response)

@twitchBot.command(name='goodbot')
async def goodBot(ctx):
    await ctx.send('MrDestructoid Just doing my job MrDestructoid')

leaderboardBot = LeaderBoardBot()

twitchThread = threading.Thread(target=twitchBot.run)
twitchThread.setDaemon(True)
twitchThread.start()
leaderboardThread = threading.Thread(target=leaderboardBot.updateDict)
leaderboardThread.setDaemon(True)
leaderboardThread.start()

while True:
    pass
