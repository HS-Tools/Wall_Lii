import threading
import os
import aiocron
import discord
from datetime import datetime
from pytz import timezone, utc
from discord.ext import commands, tasks
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
    args = list(args)

    # Handle !bgrank EU for example
    if parseRegion(args[0]):
        region = parseRegion(args[0])
        args = ['lii', region]

    # Handle if a rank is passed in with a region
    if len(args) > 1:
        args[0] = get_tag_from_rank(args[0], args[1])

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
    args = list(args)

    # Handle !bgdaily EU for example
    if parseRegion(args[0]):
        region = parseRegion(args[0])
        args = ['lii', region]

    # Handle if a rank is passed in with a region
    if len(args) > 1:
        args[0] = get_tag_from_rank(args[0], args[1])

    response = leaderboardBot.getDailyStatsText(*args)
    

    if len(args) >= 2:
        region = args[1]
        if parseRegion(region) is None:
            response = "Invalid region provided.\n" + response
    
    await ctx.send(embed = getEmbedObject(removeTwitchEmotes(response), args[0], 'daily'))

@bot.command()
async def yesterday(ctx, *args):
    args = list(args) or ['lii', None]
    args = list(args[:2])

    if len(args) == 1:
        args.append(None)
    
    args.append(True)

    # Handle !yesterday EU for example
    if parseRegion(args[0]):
        region = parseRegion(args[0])
        args = ['lii', region, True]

    # Handle if a rank is passed in with a region
    if len(args) > 1:
        args[0] = get_tag_from_rank(args[0], args[1])

    response = leaderboardBot.getDailyStatsText(*args)

    region = args[1]
    if region != None and parseRegion(region) is None:
        response = "Invalid region provided.\n" + response
    
    await ctx.send(embed = getEmbedObject(removeTwitchEmotes(response), args[0], 'yesterday'))

@bot.command()
async def goodbot(ctx):
    await ctx.send(':robot: Just doing my job :robot:')

# The machines are in UTC time, this should be 3 am ET but daylights saving may mess things up
@aiocron.crontab('59 6 * * *')
async def sendDailyRecap():
    climbers = leaderboardBot.getHighestClimbers(5)
    hardcore_gamers = leaderboardBot.getHardcoreGamers(5)

    climbersText = '**The top 5 gainers were:** \n'
    hardcore_gamersText = '**The top 5 games played were:** \n'

    for index, climber in enumerate(climbers):
        climbersText += f"{index+1}. **{climber['Tag']}** climbed a total of **{climber['Change']}** from {climber['Start']} to {climber['End']} in the {climber['Region']} region \n"

    for index, hardcore_gamer in enumerate(hardcore_gamers):
        hardcore_gamersText += f"{index+1}. **{hardcore_gamer['Tag']}** played a total of **{hardcore_gamer['Gamecount']}** games in the {hardcore_gamer['Region']} region \n"

    text = climbersText + '\n' + hardcore_gamersText

    embed = discord.Embed(title=f'Daily Recap for {get_pst_time()}', description=text)

    dedicated_channel = bot.get_channel(811468284394209300)
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()

def get_pst_time():
    date_format='%m-%d'
    date = datetime.now(tz=utc)
    date = date.astimezone(timezone('US/Pacific'))
    ptDateTime=date.strftime(date_format)
    return ptDateTime

def get_tag_from_rank(tag, region):
    try:
        if int(tag) <= 200 and int(tag) > 0 and parseRegion(region) is not None:
            rank = int(tag)
            region = parseRegion(region)

            tag = leaderboardBot.getTagFromRank(rank, region)
    except:
        pass
    return tag


leaderboardBot = LeaderBoardBot()
bot.run(os.environ['DISCORD_TOKEN'])

while True:
    pass