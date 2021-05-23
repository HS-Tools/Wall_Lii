import sys
import os
sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import data
from leaderboardBot import LeaderBoardBot
from handler import add_leaderboards_to_db
import unittest
import time

class testData(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls, fill server with data from season 2 which shouldn't change
        url = "http://localhost:8000"
        if 'ENDPOINT_URL' in os.environ.keys():
            url = os.environ['ENDPOINT_URL']

        self.database = data.RankingDatabaseClient( endpoint_url=url )

        try:
            self.database.client.delete_table(TableName='testDataTable')
        except:
            pass

        self.database.create_table('testDataTable')
        add_leaderboards_to_db(self.database, ['US'],'BG',1, False)
        self.bot = LeaderBoardBot( table_name='testDataTable', endpoint_url=url )
        self.img = self.database.table.scan()

    @classmethod
    def tearDownClass(self):
        self.database.client.delete_table(TableName='testDataTable')

    def tearDown(self):
        self.database.client.delete_table(TableName='testDataTable')
        self.database.create_table('testDataTable')
        # reload the original items
        with self.database.table.batch_writer() as batch:
            for item in self.img['Items']:
                batch.put_item(item)

    def testClearRankRemove1(self):
        self.database.put_items('US', { 'vaguerabbit':{'rank': 1, 'rating': 22483}})

        items = self.bot.getPlayerData('vaguerabbit', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

        items = self.bot.getPlayerData('ponpata07', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('ponpata07', item['PlayerName'] )
        self.assertEqual(-1, item['Rank'] )
        self.assertEqual(13626, item['Ratings'][-1] )

    def testClearRankSeason1(self):
        items = self.bot.getPlayerData('vaguerabbit', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

        items = self.bot.getPlayerData('ponpata07', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('ponpata07', item['PlayerName'] )
        self.assertEqual(51, item['Rank'] )
        self.assertEqual(13626, item['Ratings'][-1] )

        add_leaderboards_to_db(self.database, ['US'],'BG',0, False)

        items = self.bot.getPlayerData('vaguerabbit', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(-1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

        items = self.bot.getPlayerData('ponpata07', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('ponpata07', item['PlayerName'] )
        self.assertEqual(7, item['Rank'] )
        self.assertEqual(14043, item['Ratings'][-1] )

if __name__ == '__main__':
    from dotenv import load_dotenv, dotenv_values
    load_dotenv('.test-env')
    unittest.main()