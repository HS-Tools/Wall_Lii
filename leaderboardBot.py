from api import getLeaderboardSnapshot
from currentDay import getCurrentDay
from parseRegion import REGIONS, parseRegion
import threading
import requests


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

        for region in REGIONS:    
            for tag in self.currentLeaderboard[region].keys():
                currentRating = self.currentLeaderboard[region][tag]['rating']
                if tag in self.dailyStats and region in self.dailyStats[tag]:
                    lastRating = self.dailyStats[tag][region][-1]
                    if lastRating != currentRating:
                        self.dailyStats[tag][region].append(currentRating)

                        # Delete duplicate scores in case of api requests giving bad data
                        self.dailyStats[tag][region] = self.deleteDup(self.dailyStats[tag][region])
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

    def getDailyStatsText(self, tag):
        longestRecordLength = 1

        encodedTag = self.getEncodedTag(tag)
        
        if encodedTag not in self.dailyStats:
            return "{} is not on any BG leaderboards liiCat".format(encodedTag.decode())

        text = "{} and has not played any games today liiCat".format(self.getRankText(tag))

        for region in REGIONS:
            if region in self.dailyStats[encodedTag]:
                ratings = self.dailyStats[encodedTag][region]

                if len(ratings) > longestRecordLength:
                    longestRecordLength = len(ratings)
                    text = f"{encodedTag.decode()} started today at {ratings[0]} in {region} and is now {self.currentLeaderboard[region][encodedTag]['rating']} with {len(ratings)-1} games played. Their record is: {self.getDeltas(ratings)}"

        return text

    # This should only get called if ratings has more than 1 entry
    def getDeltas(self, ratings):
        lastRating = ratings[0]
        deltas = []
        
        for rating in ratings[1:]:
            deltas.append('{0:+d}'.format(rating - lastRating))

            lastRating = rating

        return ', '.join(deltas)
    

            

    def getRankText(self, tag, region = ""):
        
        if tag == 'nina' or tag == 'ninaisnoob':
            return '{} is rank 69 in Antartica with 16969 mmr ninaisFEESH'.format(tag)

        if tag == 'gomez':
            return '{} is a cat, cats do not play BG'.format(tag)

        # Resolve alias if aliased, returns None if region is invalid.
        region = parseRegion(region)
        
        if region is not None:
            specified_region = True
            regions = [region]
        else:
            specified_region = False
            regions = REGIONS

        highestRank = 9999

        encodedTag = self.getEncodedTag(tag)
        text = f"{encodedTag.decode()} is not on {region if specified_region else 'any BG'} leaderboards liiCat"
        for region in regions:
            if encodedTag in self.currentLeaderboard[region]:
                rank = self.currentLeaderboard[region][encodedTag]['rank']
                rating = self.currentLeaderboard[region][encodedTag]['rating']

                if int(rank) < highestRank:
                    highestRank = int(rank)
                    text = "{} is rank {} in {} with {} mmr liiHappyCat" \
                    .format(encodedTag.decode(), rank, region, rating)

        return text

    def deleteDup(self, lst):
        if len(lst) > 2:
            if lst[-1] == lst[-3]:
                lst = lst[-2:]

                return lst
        return lst

    def getEncodedTag(self, tag):
        tag = tag.lower()

        if tag in alias:
            tag = alias[tag]
        
        return tag.encode('utf-8')
