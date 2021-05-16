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


        self.database = data.RankingDatabaseClient(os.environ.get('TABLE_NAME'), os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'], os.environ['REGION'])
        self.database.create_table()
        snapshot, lastUpdated, season = getLeaderboardSnapshot(['US'],'BG',1, verbose=True)

        for region in snapshot.keys():
            for player in snapshot[region].keys():
                rating = snapshot[region][player]['rating']
                rank = snapshot[region][player]['rank']
                player = player.decode('utf-8')
                self.database.put_item(region=region, player=player,rating=rating,rank=rank, lastUpdate=lastUpdated[region])

        self.bot = LeaderBoardBot()

    def testGetPlayerData(self):
        items = self.bot.getPlayerData()



if __name__ == '__main__':
    unittest.main()
