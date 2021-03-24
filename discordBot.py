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
    args = args or ['lii']
    args = args[:2]

    response = leaderboardBot.getDailyStatsText(*args)

    if len(args) >= 2:
        region = args[1]
        if parseRegion(region) is None:
            response = "Invalid region provided.\n" + response
    
    await ctx.send(removeTwitchEmotes(response))

@bot.command()
async def goodbot(ctx):
    await ctx.send(':robot: Just doing my job :robot:')

leaderboardBot = LeaderBoardBot()

bot.run(os.environ['DISCORD_TOKEN'])

while True:
    pass
