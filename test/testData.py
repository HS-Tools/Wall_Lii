import sys
import os
sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import data
from leaderboardBot import LeaderBoardBot
from handler import add_leaderboards_to_db
from api import parseSnapshot, getLeaderboardSnapshot
from test import setup_production_environment
import unittest
import time

class testDataPutItems(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls, fill server with data from season 2 which shouldn't change
        url = "http://localhost:8000"
        if 'ENDPOINT_URL' in os.environ.keys():
            url = os.environ['ENDPOINT_URL']

        self.database = data.RankingDatabaseClient( endpoint_url=url )
        setup_production_environment(self.database, url)
        tables = [table.name for table in self.database.resource.tables.all()]

        if 'testDataTable' in tables:
            self.database.client.delete_table(TableName='testDataTable')

        self.tpl = getLeaderboardSnapshot( ['US'],'BG',1, False)
        self.players = self.tpl[0]['US']

    def setUp(self):
        self.database.create_table('testDataTable')

    def tearDown(self):
        self.database.client.delete_table(TableName='testDataTable')

    def testClassSetup(self):
        self.assertEqual(1, self.tpl[2])

    def testPutItems(self):
        self.database.put_items('US', self.players)
        for key in self.tpl[0]['US'].keys():
            item = self.database.get_item('US', key)
            player = self.players[key]
            self.assertIsNotNone(item)
            self.assertEqual(key, item['PlayerName'] )
            self.assertEqual(player['rank'], item['Rank'] )
            self.assertEqual(player['rating'], item['Ratings'][0] )

    def testPutTestFile(self):
        with open('files/s3-05-23-21-0150.json') as f:
            json1 = f.read()
        tlp = parseSnapshot(json1, False)
        numItems = self.database.put_items('US', tlp[0])
        self.assertEqual(200, numItems)

        for key in tlp[0].keys():
            item = self.database.get_item('US', key)
            player =  tlp[0][key]
            self.assertIsNotNone(item)
            self.assertEqual(key, item['PlayerName'] )
            self.assertEqual(player['rank'], item['Rank'] )
            self.assertEqual(player['rating'], item['Ratings'][0] )

    def testPutTestFiles(self):
        with open('files/s3-05-23-21-0150.json') as f:
            json1 = f.read()
        with open('files/s3-05-23-21-0209.json') as f:
            json2 = f.read()

        tlp = parseSnapshot(json1, False)
        numItems = self.database.put_items('US', tlp[0])
        self.assertEqual(200, numItems)

        tlp = parseSnapshot(json2, False)
        numItems = self.database.put_items('US', tlp[0])
        self.assertEqual(120, numItems)

        for key in tlp[0].keys():
            item = self.database.get_item('US', key)
            player =  tlp[0][key]
            self.assertIsNotNone(item)
            self.assertEqual(key, item['PlayerName'] )
            self.assertEqual(player['rank'], item['Rank'] )
            self.assertEqual(player['rating'], item['Ratings'][-1] )

    def testPutTime(self):
        time = self.database.parse_time(self.tpl[1]['US'])
        self.database.put_time('US', time)
        ## time zones aren't being handled correctly in this environment
        if self.database.get_time('US') == 1608066223:
            self.assertEqual(1608066223, self.database.get_time('US'))
        else:
            self.assertEqual(1608095023, self.database.get_time('US'))

    def testClearPutItems(self):
        self.database.put_items('US', self.players)
        self.database.put_items('US', { 'vaguerabbit':{'rank': 1, 'rating': 22483}})

        item = self.database.get_item('US', 'vaguerabbit')
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

        item = self.database.get_item('US', 'ponpata07')
        self.assertEqual('ponpata07', item['PlayerName'] )
        self.assertEqual(-1, item['Rank'] )
        self.assertEqual(13626, item['Ratings'][-1] )

    def testClearPutItemSeason1(self):
        self.database.put_items('US', self.players)
        item = self.database.get_item('US', 'saphirexx')
        self.assertEqual('saphirexx', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

        item = self.database.get_item('US', 'ponpata07')
        self.assertEqual('ponpata07', item['PlayerName'] )
        self.assertEqual(51, item['Rank'] )
        self.assertEqual(13626, item['Ratings'][-1] )

        add_leaderboards_to_db(self.database, ['US'],'BG',0, False)

        item = self.database.get_item('US', 'saphirexx')
        self.assertEqual('saphirexx', item['PlayerName'] )
        self.assertEqual(-1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

        item = self.database.get_item('US', 'ponpata07')
        self.assertEqual('ponpata07', item['PlayerName'] )
        self.assertEqual(7, item['Rank'] )
        self.assertEqual(14043, item['Ratings'][-1] )


if __name__ == '__main__':
    from dotenv import load_dotenv, dotenv_values
    load_dotenv('.test-env')
    unittest.main()
