from api import getLeaderboardSnapshot
import requests
import threading
import time
import json
import schedule
import os
from sys import exit
from twitchio.ext import commands

regions = ['US', 'EU', 'AP']
channels = ['IamTehShadow', 'DominickStarcraft', 'Xixo', 'LiiHS', 'Hapabear', 'ninaisnoob', 'PockyPlays', 'Blirby', 'MrIncredibleHS', 'VendettaHSB', 'Jkirek_', 'DeathItselfHS', 'Livvylive']
alias = {
    'waterloo': 'waterloooooo',
    'jeef': 'jeffispro',
    'jeff': 'jeffispro',
    'victor': 'diyingli',
    'sleepy': 'foreversleep'
}
currentLeaderboard = {}
record = []
startRating = 0
currentRating = 0

def updateDict():
    global currentLeaderboard
    global record
    global startRating
    global currentRating

    newRating = 0
    
    try:
        currentLeaderboard = getLeaderboardSnapshot()
    except requests.ConnectionError as e:
        print(str(e))
        
    try:
        newRating = currentLeaderboard['US']['lii'.encode('utf-8')]['rating']
        if startRating == 0:
            startRating = newRating
            currentRating = newRating
            writeToFile(newRating)

        if newRating != currentRating:
            delta = int(newRating) - int(currentRating)
            currentRating = newRating

            if delta > 0:
                deltaText = "+" + str(delta)
            elif delta < 0:
                deltaText = str(delta)
            else:
                deltaText = ''

            if deltaText:
                record.append(deltaText)

            writeToFile(newRating)

        print('total people fetched in the us ' + str(len(currentLeaderboard['US'].keys())))
    except KeyError:
        print('failed to find lii')

    t = threading.Timer(150, updateDict)
    t.start()

def writeToFile(mmr):
    global record
    global startRating

    if mmr == 0:
        return

    wr = open('record.txt', 'w')
    wr.write('Start: {}\n\n'.format(startRating))
    wr.write('Current: {}\n\nRecord:\n'.format(mmr))
    for r in record:
        wr.write(r + '\n')

def updateThreaded():
    global updateDict
    schedulerThread = threading.Thread(target=updateDict)
    schedulerThread.daemon = True

def getResponseText(tag):
    global regions
    global currentLeaderboard

    highestRank = 9999
    #only changes if an alias is used
    originalTag = tag

    if tag in alias:
        tag = alias[tag]
        originalTag = tag
    
    if tag == 'nina' or tag == 'ninaisnoob':
        return '{} is rank 69 in Antartica with 16969 mmr liiSwag'.format(tag)

    encodedTag = tag.encode('utf-8')
    text = "{} is not on any BG leaderboards liiCat".format(tag)
    for region in regions:
        if encodedTag in currentLeaderboard[region]:
            rank = currentLeaderboard[region][encodedTag]['rank']
            rating = currentLeaderboard[region][encodedTag]['rating']

            if int(rank) < highestRank:
                highestRank = int(rank)
                text = "{} is rank {} in {} with {} mmr liiHappyCat" \
                .format(originalTag, rank, region, rating)

    return text

bot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=channels
)

@bot.event
async def event_message(ctx):
    # make sure the bot ignores itself and the streamer
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
        return
    await bot.handle_commands(ctx)

@bot.command(name='bgrank')
async def getRank(ctx):
    global currentLeaderboard

    if len(ctx.content.split(' ')) > 1:
        tag = ctx.content.split(' ')[1].lower()

        response = getResponseText(tag)

        await ctx.send(response)
    else :
        response = getResponseText('lii')

        await ctx.send(response)

@bot.command(name='goodbot')
async def goodBot(ctx):
    await ctx.send('MrDestructoid Just doing my job MrDestructoid')

# Run a thread for the bot
botThread = threading.Thread(target=bot.run)
botThread.daemon = True
botThread.start()

updateDict()
