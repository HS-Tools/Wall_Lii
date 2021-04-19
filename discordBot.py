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

def getEmbedObject(text, player, command):
    embed = discord.Embed(title=f'{player}\'s {command}', description=text)

    return embed

def removeTwitchEmotes(s):
    for key in emotes:
        s = s.replace(key, '')

    return s

@bot.command()
async def bgrank(ctx, *args):
    args = args or ['lii']
    args = args[:2]

    # Handle !bgrank EU for example
    if parseRegion(args[0]):
        region = parseRegion(args[0])
        args = ['lii', region]

    response = removeTwitchEmotes(leaderboardBot.getRankText(*args))

    if len(args) >= 2:
        region = args[1]
        if parseRegion(region) is None:
            response = "Invalid region provided.\n" + response
        
    await ctx.send(embed = getEmbedObject(removeTwitchEmotes(response), args[0], 'rank'))

@bot.command()
async def bgdaily(ctx, *args):
    args = args or ['lii']
    args = args[:2]

    # Handle !bgdaily EU for example
    if parseRegion(args[0]):
        region = parseRegion(args[0])
        args = ['lii', region]

    response = leaderboardBot.getDailyStatsText(*args)

    if len(args) >= 2:
        region = args[1]
        if parseRegion(region) is None:
            response = "Invalid region provided.\n" + response
    
    await ctx.send(embed = getEmbedObject(removeTwitchEmotes(response), args[0], 'daily'))

@bot.command()
async def goodbot(ctx):
    await ctx.send(':robot: Just doing my job :robot:')

leaderboardBot = LeaderBoardBot()
print(leaderboardBot.getHighestClimbers(5))
print(leaderboardBot.getHardcoreGamers(5))

bot.run(os.environ['DISCORD_TOKEN'])

while True:
    pass