from api import getLeaderboardSnapshot
from currentDay import getCurrentDay
import requests
import threading
import time
import json
import schedule
import os
from multiprocessing import Process
from sys import exit
import discord
import asyncio
from twitchio.ext import commands

regions = ['US', 'EU', 'AP']
channels = {'iamtehshadow': 'tehshadow', 
'dominickstarcraft': 'Dom2805',
'rolferolferolfe': 'rolfe',
'jeeeeeeef': 'jeef',
'xixo': 'xixo',
'terry_tsang_gaming': 'terrytsang',
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

    def checkIfNewDay(self):
        if getCurrentDay() != self.currentDay:
            self.currentDay = getCurrentDay()

            self.dailyStats = {}
            return True

        return False

    def updateDailyStats(self):
        # I will need to account for people that have the same account name multiple times in the leaderboard in the future

        for region in regions:    
            for tag in self.currentLeaderboard[region].keys():
                currentRating = self.currentLeaderboard[region][tag]['rating']
                if tag in self.dailyStats and region in self.dailyStats[tag]:
                    lastRating = self.dailyStats[tag][region][-1]
                    if lastRating != currentRating:
                        self.dailyStats[tag][region].append(currentRating)
                elif tag in self.dailyStats and region not in self.dailyStats[tag]:
                    self.dailyStats[tag][region] = [currentRating]
                elif tag not in self.dailyStats:
                    self.dailyStats[tag] = {region: [currentRating]}
                
    def updateDict(self):
        try:
            self.currentLeaderboard = getLeaderboardSnapshot()
            self.updateDailyStats()
            self.checkIfNewDay()
            print('Fetched {} people in the US'.format(str(len(self.currentLeaderboard['US'].keys()))))
        except requests.ConnectionError as e:
            print(str(e))

        t = threading.Timer(150, self.updateDict)
        t.start()

    # def updateThreaded(self):
    #     schedulerThread = threading.Thread(target=self.updateDict)
    #     schedulerThread.daemon = True
    #     schedulerThread.start()

    def getDailyStatsText(self, tag):
        longestRecordLength = 1

        encodedTag = self.getEncodedTag(tag)
        
        if encodedTag not in self.dailyStats:
            return "{} is not on any BG leaderboards liiCat".format(encodedTag.decode())

        text = "{} and has not played any games today liiCat".format(self.getRankText(tag))

        for region in regions:
            if region in self.dailyStats[encodedTag]:
                ratings = self.dailyStats[encodedTag][region]

                if len(ratings) > longestRecordLength:
                    longestRecordLength = len(ratings)
                    text = "{} started today at {} in {} and is now {} with {} games played. Their record is: {}".format(encodedTag.decode(), ratings[0], region, self.currentLeaderboard[region][encodedTag]['rating'], len(ratings)-1, self.getDeltas(ratings))

        return text

    # This should only get called if ratings has more than 1 entry
    def getDeltas(self, ratings):
        lastRating = ratings[0]
        deltas = []
        
        for rating in ratings[1:]:
            deltas.append('{0:+d}'.format(rating - lastRating))

            lastRating = rating

        return ', '.join(deltas)
            

    def getRankText(self, tag):
        highestRank = 9999

        if tag == 'nina' or tag == 'ninaisnoob':
            return '{} is rank 69 in Antartica with 16969 mmr ninaisFEESH'.format(tag)

        if tag == 'gomez':
            return '{} is a cat, cats do not play BG'.format(tag)

        encodedTag = self.getEncodedTag(tag)
        text = "{} is not on any BG leaderboards liiCat".format(encodedTag.decode())
        for region in regions:
            if encodedTag in self.currentLeaderboard[region]:
                rank = self.currentLeaderboard[region][encodedTag]['rank']
                rating = self.currentLeaderboard[region][encodedTag]['rating']

                if int(rank) < highestRank:
                    highestRank = int(rank)
                    text = "{} is rank {} in {} with {} mmr liiHappyCat" \
                    .format(encodedTag.decode(), rank, region, rating)

        return text

    def getEncodedTag(self, tag):
        if tag in alias:
            tag = alias[tag]
        
        return tag.encode('utf-8')

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

        response = leaderboardBot.getRankText(tag)

        await ctx.send(response)
    else :
        response = leaderboardBot.getRankText(channels[ctx.channel.name])

        await ctx.send(response)

@twitchBot.command(name='bgdaily')
async def getDailyStats(ctx):
    if len(ctx.content.split(' ')) > 1:
        tag = ctx.content.split(' ')[1].lower()

        response = leaderboardBot.getDailyStatsText(tag)

        await ctx.send(response)
    else :
        response = leaderboardBot.getDailyStatsText(channels[ctx.channel.name])

        await ctx.send(response)

@twitchBot.command(name='goodbot')
async def goodBot(ctx):
    await ctx.send('MrDestructoid Just doing my job MrDestructoid')

leaderboardBot = LeaderBoardBot()
discordBot = discord.Client()

@discordBot.event
async def on_ready():
    print('{} connected to discord'.format(discordBot.user))

@discordBot.event
async def on_message(message):
    if message.author == discordBot.user:
        return

    if message.content == '99!':
        await message.channel.send('hi')

# loop = asyncio.get_event_loop()
# loop.create_task(leaderboardBot.updateDict())
# loop.create_task(twitchBot.start())
# loop.create_task(discordBot.run(os.environ['DISCORD_TOKEN']))
# loop.run_forever()

# threading.Thread(target=leaderboardBot.updateDict).start()
# threading.Thread(target=discordBot.run, args=(os.environ['DISCORD_TOKEN'])).start()
# threading.Thread(target=twitchBot.run).start()

# threading.Thread(target=discordBot.run, args=[os.environ['DISCORD_TOKEN']]).start()
twitchThread = threading.Thread(target=twitchBot.run)
twitchThread.setDaemon(True)
twitchThread.start()
leaderboardThread = threading.Thread(target=leaderboardBot.updateDict)
leaderboardThread.setDaemon(True)
leaderboardThread.start()
discordThread = threading.Thread(target=discordBot.run, args=[os.environ['DISCORD_TOKEN']])
discordThread.setDaemon(True)
discordThread.start()

while True:
    pass
