import os
import threading
from twitchio.ext import commands
from leaderboardBot import LeaderBoardBot
from parseRegion import parseRegion, isRegion
from dotenv import load_dotenv

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
'saphirexx': 'vaguerabbit',
'sunglitters': 'sunglitters',
'sevel07': 'sevel',
'endozoa': 'endozoa',
'ixxdeee': 'ixxdeee',
'l0rinda': 'l0rinda',
'honinbo7': 'honinbo7',
'sassyrutabaga1': 'rutabaga',
'tylerootd': 'tyler',
'hapabear': 'hapabear',
'nicholena': 'hiddensquid',
'ninaisnoob': 'ninaisnoob',
'pockyplays': 'pocky',
'blirby': 'blirby',
'mrincrediblehs': 'mrincredible',
'vendettahsb': 'vendetta',
'jkirek_': 'jkirek',
'deathitselfhs': 'deathitself',
'livvylive': 'livvy',
'duhbbleyou': 'theletterw',
'purple_hs': 'purple',
'hmcnation': 'hurrymycurry',
'wumbostyle': 'wumbostyle',
'bradwong_live': 'bradwong',
'bofur_hs': 'bofur',
'malisarhs': 'malisar',
'mcmariners': 'mcmariners',
'swissguy93': 'swissguy',
'grinninggoat': 'merps',
'zorgo_hs': 'zorg',
'kita_731': 'kita',
'fasteddietwitch': 'fasteddie',
'benice92': 'benice',
'runfree_aa': 'runfreeaa',
'glory_to_god': 'glorytogod',
'sunbaconrelaxer': 'victor',
'slysssa': 'slysssa'}

load_dotenv()

twitchBot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=channels.keys()
)


def parseArgs(ctx):
    default = channels[ctx.channel.name]
    return leaderboardBot.parseArgs(default, ctx.content.split(' ')[1:])

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

leaderboardBot = LeaderBoardBot()

twitchThread = threading.Thread(target=twitchBot.run)
twitchThread.setDaemon(True)
twitchThread.start()

while True:
    pass
