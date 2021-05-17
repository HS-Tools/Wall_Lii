import sys
import os
sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import data
from api import getLeaderboardSnapshot
from leaderboardBot import LeaderBoardBot
import unittest

class apiLeaaderboard(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls, fill server with data from season 2 which shouldn't change

        ## ,
        os.environ['AWS_ACCESS_KEY_ID'] = 'DUMMYIDEXAMPLE'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'DUMMYEXAMPLEKEY'
        os.environ['REGION'] = 'us-west-2'
        os.environ['TABLE_NAME'] = 'testTable'
        url = "http://localhost:8000"
        if 'ENDPOINT_URL' in os.environ.keys():
            url = os.environ['ENDPOINT_URL']

        self.database = data.RankingDatabaseClient( url )
        try:
            self.database.create_table()
            snapshot, lastUpdated, season = getLeaderboardSnapshot(['US'],'BG',1, verbose=True)
            for region in snapshot.keys():
                for player in snapshot[region].keys():
                    rating = snapshot[region][player]['rating']
                    rank = snapshot[region][player]['rank']
                    player = player.decode('utf-8')
                    self.database.put_item(region=region, player=player,rating=rating,rank=rank, lastUpdate=lastUpdated[region])

        except Exception as e:
            print('exception',e)
            print("table was not created, assume it exists")

        self.bot = LeaderBoardBot( url=url )

    def testGetPlayerData(self):
        items = self.bot.getPlayerData('vaguerabbit', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

    def testGetRankNumData(self):
        items = self.bot.getRankNumData(1, self.bot.table, 'US' )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

    def testGetRankNumText(self):
        string = self.bot.getRankNumText(1,'US')
        # self.assertIn()



if __name__ == '__main__':
    unittest.main()
