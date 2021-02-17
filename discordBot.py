import threading
import os
import discord
from discord.ext import commands
from leaderboardBot import LeaderBoardBot

discordBot = discord.Client()
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
    if len(args) == 0:
        response = leaderboardBot.getRankText('lii')
        await ctx.send(removeTwitchEmotes(response))

        return

    response = leaderboardBot.getRankText(args[0])

    await ctx.send(removeTwitchEmotes(response))

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

discordThread = threading.Thread(target=bot.run, args=[os.environ['DISCORD_TOKEN']])
discordThread.setDaemon(True)
discordThread.start()
leaderboardBot = LeaderBoardBot()
leaderboardThread = threading.Thread(target=leaderboardBot.updateDict)
leaderboardThread.setDaemon(True)
leaderboardThread.start()

while True:
    pass
