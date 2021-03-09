import threading
import os
import discord
from discord.ext import commands
from leaderboardBot import LeaderBoardBot
from parseRegion import parseRegion

bot = commands.Bot(command_prefix='!')

emotes = [
    'liiHappyCat',
    'liiCat',
    'ninaisFEESH'
]


def removeTwitchEmotes(s):
    for key in emotes:
        s = s.replace(key, '')

    return s

@bot.command()
async def bgrank(ctx, *args):
    
    invalid_region = False
    args = args or ['lii']
    args = args[:2]

    response = removeTwitchEmotes(leaderboardBot.getRankText(*args))

    if len(args) >= 2:
        region = args[1]
        if parseRegion(region) is None:
            response = "Invalid region provided.\n" + response
        
    await ctx.send(response)

@bot.command()
async def bgdaily(ctx, *args):
    if len(args) == 0:
        response = leaderboardBot.getDailyStatsText('lii')
        await ctx.send(removeTwitchEmotes(response))

        return

    response = leaderboardBot.getDailyStatsText(args[0])
    
    await ctx.send(removeTwitchEmotes(response))

@bot.command()
async def goodbot(ctx):
    await ctx.send(':robot: Just doing my job :robot:')

#discordThread = threading.Thread(target=bot.run, args=[os.environ['DISCORD_TOKEN']])
#discordThread.setDaemon(True)
#discordThread.start()
leaderboardBot = LeaderBoardBot()
leaderboardThread = threading.Thread(target=leaderboardBot.updateDict)
leaderboardThread.setDaemon(True)
leaderboardThread.start()

bot.run(os.environ['DISCORD_TOKEN'])

while True:
    pass
