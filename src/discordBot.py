import threading
import os
import aiocron
import discord
from datetime import datetime
from pytz import timezone, utc
from discord.ext import commands, tasks
from leaderboardBot import LeaderBoardBot
from parseRegion import parseRegion, isRegion
from dotenv import load_dotenv
load_dotenv()

bot = commands.Bot(command_prefix='!')

emotes = [
    'liiHappyCat',
    'liiCat',
    'ninaisFEESH',
    'liiWait'
]

def getEmbedObject(text, player, command):
    embed = discord.Embed(title=f'{player}\'s {command}', description=text)

    return embed

def removeTwitchEmotes(s):
    for key in emotes:
        s = s.replace(key, '')
    return s

async def call(ctx, func, name, *args):
    response = removeTwitchEmotes(func(*args))
    if len(args) >= 2:
        if not isRegion(args[1]):
            response = "Invalid region provided.\n" + response
    await ctx.send(embed = getEmbedObject(response, args[0], name))

@bot.command()
async def bgrank(ctx, *args):
    args = leaderboardBot.parseArgs('lii', *args)
    await call(ctx, leaderboardBot.getRankText, 'rank', *args)

@bot.command()
async def bgdaily(ctx, *args):
    args = leaderboardBot.parseArgs('lii', *args)
    await call(ctx, leaderboardBot.getDailyStatsText, 'daily', *args)

@bot.command()
async def yesterday(ctx, *args):
    args = leaderboardBot.parseArgs('lii', *args)
    args.append(True)   ## send the yesterday value to the function
    await call(ctx, leaderboardBot.getDailyStatsText, 'yesterday', *args)

@bot.command()
async def goodbot(ctx):
    await ctx.send(':robot: Just doing my job :robot:')

@bot.command()
async def addalias(ctx, *args):
    if (ctx.message.channel.id == 846867129834930207):
        if len(args) < 2:
            await ctx.send('The command must have two words. !addalias [alias] [name]')
        else:
            alias = args[0].lower()
            name = args[1].lower()
        
            leaderboardBot.addAlias(alias, name)
            leaderboardBot.updateAlias()
            await ctx.send(f'{alias} is now an alias for {name}')

@bot.command()
async def addchannel(ctx, *args):
    if (ctx.message.channel.id == 846867129834930207):
        if len(args) < 2:
            await ctx.send('The command must have two words. !addchannel [channelName] [playerName]')
        else:
            channelName = args[0].lower()
            playerName = args[1].lower()

            leaderboardBot.addChannel(channelName, playerName)
            
            await ctx.send(f'{channelName} will have wall_lii added to it in around an hour with the name {playerName}')

# PI is on UTC time it seems
@aiocron.crontab('59 6 * * *')
async def sendDailyRecap():
    climbers = leaderboardBot.getMostMMRChanged(5, True)
    losers = leaderboardBot.getMostMMRChanged(5, False)
    hardcore_gamers = leaderboardBot.getHardcoreGamers(5)
    highest_active = leaderboardBot.getHighestRatingAndActivePlayers(5)

    climbersText = '**The top 5 climbers were:** \n'
    losersText = '**The top 5 unluckiest were:** \n'
    hardcore_gamersText = '**The top 5 grinders were:** \n'
    highestText = '**The top 5 highest rated active players today were:** \n'

    for index, climber in enumerate(climbers):
        climbersText += f"{index+1}. **{climber['Tag']}** climbed a total of **{climber['Change']}** from {climber['Start']} to {climber['End']} in the {climber['Region']} region \n"

    for index, loser in enumerate(losers):
        losersText += f"{index+1}. **{loser['Tag']}** lost a total of **{abs(loser['Change'])}** from {loser['Start']} to {loser['End']} in the {loser['Region']} region \n"

    for index, hardcore_gamer in enumerate(hardcore_gamers):
        hardcore_gamersText += f"{index+1}. **{hardcore_gamer['Tag']}** played a total of **{hardcore_gamer['Gamecount']}** games in the {hardcore_gamer['Region']} region \n"

    for index, highest in enumerate(highest_active):
        highestText += f"{index+1}. **{highest['Tag']}** went from **{highest['Start']}** to **{highest['End']}** in the {highest['Region']} region \n"

    text = climbersText + '\n' + losersText + '\n' + hardcore_gamersText + '\n' + highestText

    embed = discord.Embed(title=f'Daily Liiderboards for {get_pst_time()}', description=text)

    dedicated_channel = bot.get_channel(811468284394209300)
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()

@bot.command()
async def test1(ctx):
    climbers = leaderboardBot.getMostMMRChanged(5, True)
    losers = leaderboardBot.getMostMMRChanged(5, False)
    hardcore_gamers = leaderboardBot.getHardcoreGamers(5)
    highest_active = leaderboardBot.getHighestRatingAndActivePlayers(5)

    climbersText = '**The top 5 climbers were:** \n'
    losersText = '**The top 5 unluckiest were:** \n'
    hardcore_gamersText = '**The top 5 grinders were:** \n'
    highestText = '**The top 5 highest rated active players were:** \n'

    for index, climber in enumerate(climbers):
        climbersText += f"{index+1}. **{climber['Tag']}** climbed a total of **{climber['Change']}** from {climber['Start']} to {climber['End']} in the {climber['Region']} region \n"

    for index, loser in enumerate(losers):
        losersText += f"{index+1}. **{loser['Tag']}** lost a total of **{abs(loser['Change'])}** from {loser['Start']} to {loser['End']} in the {loser['Region']} region \n"

    for index, hardcore_gamer in enumerate(hardcore_gamers):
        hardcore_gamersText += f"{index+1}. **{hardcore_gamer['Tag']}** played a total of **{hardcore_gamer['Gamecount']}** games in the {hardcore_gamer['Region']} region \n"

    for index, highest in enumerate(highest_active):
        highestText += f"{index+1}. **{highest['Tag']}** went from **{highest['Start']}** to **{highest['End']}** in the {highest['Region']} region \n"

    text = climbersText + '\n' + losersText + '\n' + hardcore_gamersText + '\n' + highestText

    embed = discord.Embed(title=f'Daily Liiderboards for {get_pst_time()}', description=text)

    dedicated_channel = bot.get_channel(730782280674443327)
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()

def get_pst_time():
    date_format='%m-%d'
    date = datetime.now(tz=utc)
    date = date.astimezone(timezone('US/Pacific'))
    ptDateTime=date.strftime(date_format)
    return ptDateTime

if __name__ == '__main__':
    leaderboardBot = LeaderBoardBot()
    leaderboardBot.updateAlias()

    bot.run(os.environ['DISCORD_TOKEN'])

    @aiocron.crontab('5 * * * *') ## Every hour on the 5 check and update the alias table
    def updateAlias():
        leaderboardbot.updateAlias()

    while True:
        pass
