from leaderboardSnapshot import getLeaderboardSnapshot
import threading
import time
import schedule
import os
from sys import exit
from twitchio.ext import commands

regions = ['US', 'EU', 'AP']
currentLeaderboard = {}
record = []
startRating = 0

def updateDict():
    global currentLeaderboard
    global record
    global startRating

    oldRating = 0

    if currentLeaderboard:
        try:
            oldRating = currentLeaderboard['US']['lii'.encode('utf-8')]['rating']
        except KeyError:
            print('failed to find lii')
            exit()

    currentLeaderboard = getLeaderboardSnapshot()
    try:
        newRating = currentLeaderboard['US']['lii'.encode('utf-8')]['rating']
        if startRating == 0:
            startRating = newRating
    except KeyError:
        print('failed to find lii')
        exit()

    if oldRating:
        delta = int(newRating) - int(oldRating)

        if delta > 0:
            deltaText = "+" + str(delta)
        elif delta < 0:
            deltaText = str(delta)
        else:
            deltaText = ''

        if deltaText:
            record.append(deltaText)

    writeToFile(newRating)
    print('Finished fetching leaderboard')

def writeToFile(mmr):
    global record
    global startRating

    wr = open('record.txt', 'w')
    wr.write('Start: {}\n'.format(startRating))
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
    encodedTag = tag.encode('utf-8')
    text = "{} is not on any BG leaderboards".format(tag)
    for region in regions:
        if encodedTag in currentLeaderboard[region]:
            rank = currentLeaderboard[region][encodedTag]['rank']
            rating = currentLeaderboard[region][encodedTag]['rating']

            if int(rank) < highestRank:
                highestRank = int(rank)
                text = "{} is rank {} in {} with {} mmr" \
                .format(tag, rank, region, rating)

    return text

bot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=[os.environ['CHANNEL']]
)

@bot.event
async def event_ready():
    ws = bot._ws

@bot.command(name='bgrank')
async def getRank(ctx):
    global currentLeaderboard

    if len(ctx.content.split(' ')) > 1:
        tag = ctx.content.split(' ')[1].lower()
        response = getResponseText(tag)

        await ctx.send(response)

# Run a thread for the bot
botThread = threading.Thread(target=bot.run)
botThread.daemon = True
botThread.start()

# Get leaderboards on start
updateDict()

# Update leaderboards dict every 10 mins
schedule.every(1).minutes.do(updateThreaded)

while True:
    schedule.run_pending()
    # So CPU usage isn't hogged
    time.sleep(1)
    
