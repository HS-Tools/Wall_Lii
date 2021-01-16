from leaderboardSnapshot import getLeaderboardSnapshot
import threading
import time
import schedule
import os
from sys import exit
from twitchio.ext import commands

regions = ['US', 'EU', 'AP']
currentLeaderboard = {}

def updateDict():
    global currentLeaderboard

    currentLeaderboard = getLeaderboardSnapshot()
    print('Finished fetching leaderboard')

def updateThreaded(thread):
    thread.start()

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
        tag = ctx.content.split(' ')[1]
        response = getResponseText(tag)

        await ctx.send(response)

# Run a thread for the bot
botThread = threading.Thread(target=bot.run)
botThread.daemon = True
botThread.start()

# Get leaderboards on start
updateDict()

# Update leaderboards dict every 10 mins
schedulerThread = threading.Thread(target=updateDict)
schedulerThread.daemon = True
schedule.every(10).minutes.do(updateThreaded, schedulerThread)

while True:
    schedule.run_pending()
    # So CPU usage isn't hogged
    time.sleep(1)
    
