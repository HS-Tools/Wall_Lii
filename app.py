from api import getLeaderboardSnapshot
from currentDay import getCurrentDay
import requests
import threading
import time
import json
import schedule
import os
from sys import exit
from twitchio.ext import commands

regions = ['US', 'EU', 'AP']
channels = {'iamtehshadow': 'tehshadow', 
'dominickstarcraft': 'Dom2805',
'rolferolferolfe': 'rolfe',
'jeeeeeeef': 'jeef',
'xixo': 'xixo',
'liihs': 'lii', 
'endozoa': 'endozoa',
'hapabear': 'hapabear',
'ninaisnoob': 'ninaisnoob',
'pockyplays': 'pocky',
'blirby': 'blirby',
'mrincrediblehs': 'mrincredible',
'vendettahsb': 'vendetta',
'jkirek_': 'jkirek',
'deathitselfhs': 'deathitself',
'livvylive': 'livvy',
'bofur_hs': 'bofur'}

alias = {
    'waterloo': 'waterloooooo',
    'jeef': 'jeffispro',
    'jeff': 'jeffispro',
    'victor': 'diyingli',
    'sleepy': 'foreversleep'
}

class LeaderBoardBot:
    currentDay = None
    currentLeaderboard = {}
    dailyStats = {}
    record = []

    def __init__(self):
        self.currentDay = getCurrentDay()
        self.updateDict()

    def checkIfNewDay(self):
        if getCurrentDay() != self.currentDay:
            self.currentDay = getCurrentDay()
            return True

        return False

    def updateDailyStats(self):
        return
        # for key in self.currentLeaderboard:

    def updateDict(self):
        try:
            self.currentLeaderboard = getLeaderboardSnapshot()
            print('Fetched {} people in the US'.format(str(len(self.currentLeaderboard['US'].keys()))))

        except requests.ConnectionError as e:
            print(str(e))

        t = threading.Timer(150, self.updateDict)
        t.start()

    def updateThreaded(self):
        schedulerThread = threading.Thread(target=self.updateDict)
        schedulerThread.daemon = True

    def getResponseText(self, tag):
        highestRank = 9999
        #only changes if an alias is used
        originalTag = tag

        if tag in alias:
            tag = alias[tag]
            originalTag = tag
        
        if tag == 'nina' or tag == 'ninaisnoob':
            return '{} is rank 69 in Antartica with 16969 mmr ninaisFEESH'.format(tag)

        if tag == 'gomez':
            return '{} is a cat, cats do not play BG'.format(tag)

        encodedTag = tag.encode('utf-8')
        text = "{} is not on any BG leaderboards liiCat".format(tag)
        for region in regions:
            if encodedTag in self.currentLeaderboard[region]:
                rank = self.currentLeaderboard[region][encodedTag]['rank']
                rating = self.currentLeaderboard[region][encodedTag]['rating']

                if int(rank) < highestRank:
                    highestRank = int(rank)
                    text = "{} is rank {} in {} with {} mmr liiHappyCat" \
                    .format(originalTag, rank, region, rating)

        return text

leaderboardBot = LeaderBoardBot()

twitchBot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=channels.keys()
)

@twitchBot.event
async def event_message(ctx):
    # make sure the bot ignores itself and the streamer
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
        return
    await twitchBot.handle_commands(ctx)

@twitchBot.command(name='bgrank')
async def getRank(ctx):
    if len(ctx.content.split(' ')) > 1:
        tag = ctx.content.split(' ')[1].lower()

        response = leaderboardBot.getResponseText(tag)

        await ctx.send(response)
    else :
        response = leaderboardBot.getResponseText(channels[ctx.channel.name])

        await ctx.send(response)

@twitchBot.command(name='goodbot')
async def goodBot(ctx):
    await ctx.send('MrDestructoid Just doing my job MrDestructoid')

# Run a thread for the bot
twitchBotThread = threading.Thread(target=twitchBot.run)
twitchBotThread.daemon = True
twitchBotThread.start()
