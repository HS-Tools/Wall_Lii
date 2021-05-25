import sys
import os
sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import data
from handler import add_leaderboards_to_db
from leaderboardBot import LeaderBoardBot
import unittest

class testLeaderboardGet(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls, fill server with data from season 2 which shouldn't change
        url = "http://localhost:8000"
        if 'ENDPOINT_URL' in os.environ.keys():
            url = os.environ['ENDPOINT_URL']

        self.database = data.RankingDatabaseClient( endpoint_url=url )
        tables = [table.name for table in self.database.resource.tables.all()]

        if 'player-alias-table' in tables:
            self.database.client.delete_table(TableName='player-alias-table')

        try:
            self.database.client.delete_table(TableName='testLeaderboardBot')
        except:
            pass

        self.database.create_table('testLeaderboardBot')
        add_leaderboards_to_db(self.database, ['US'],'BG',1, False)

        self.bot = LeaderBoardBot( table_name='testLeaderboardBot', endpoint_url=url )
        self.img = self.database.table.scan()

    @classmethod
    def tearDownClass(self):
        self.database.client.delete_table(TableName = 'testLeaderboardBot')

    def testGetPlayerData(self):
        items = self.bot.getPlayerData('vaguerabbit', self.bot.table )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

    def testGetRankNumData(self):
        items = self.bot.getEntryFromRank(1, 'US' )
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual('vaguerabbit', item['PlayerName'] )
        self.assertEqual(1, item['Rank'] )
        self.assertEqual(22483, item['Ratings'][0] )

    def testGetRankNumText(self):
        string = self.bot.getRankText('1','US')
        self.assertIn('vaguerabbit ', string)
        self.assertIn(' 22483 ', string)
        self.assertIn(' 1 ', string)

    def testGetRankNumTextAlt(self):
        string = self.bot.getRankText('2','NA')
        self.assertIn('testmmr ', string)
        self.assertIn(' 22019 ', string)
        self.assertIn(' 2 ', string)

    def testGetRankNumEgg(self):
        string = self.bot.getRankText('420','NA')
        self.assertEqual("don't do drugs kids", string)

    def testGetRankText(self):
        string = self.bot.getRankText('vaguerabbit', 'US')
        self.assertIn('vaguerabbit ', string)
        self.assertIn(' 22483 ', string)
        self.assertIn(' 1 ', string)

    def testGetRankTextAlt(self):
        string = self.bot.getRankText(*('TestMMR', 'NA'))
        self.assertIn('testmmr ', string)
        self.assertIn(' 22019 ', string)
        self.assertIn(' 2 ', string)

    def testGetRankTextNum(self):
        string = self.bot.getRankText('1','US')
        self.assertIn('vaguerabbit ', string)
        self.assertIn(' 22483 ', string)
        self.assertIn(' 1 ', string)

    def testGetRankTextNoRegion(self):
        string = self.bot.getRankText('vaguerabbit')
        self.assertIn('vaguerabbit ', string)
        self.assertIn(' 22483 ', string)
        self.assertIn(' 1 ', string)

    def testParseArgDefault(self):
        args = self.bot.parseArgs('lii')
        self.assertEqual('lii', args[0])
        self.assertIsNone(args[1])

    def testParseArgName(self):
        args = self.bot.parseArgs('lii', 'quinnabr',)
        self.assertEqual('quinnabr', args[0])
        self.assertIsNone(args[1])

    def testParseArgRegion(self):
        args = self.bot.parseArgs('lii', 'EU', )
        self.assertEqual('lii', args[0])
        self.assertEqual('EU', args[1])

    def testParseArgUserRegion(self):
        args = self.bot.parseArgs('lii', 'quinnabr', 'EU', )
        self.assertEqual('quinnabr', args[0])
        self.assertEqual('EU', args[1])

    def testAliasJeef(self):
        print(self.bot.alias)
        string = self.bot.getRankText('jeef')
        self.assertIn('jeffispro ', string)
        self.assertIn(' 16033 ', string)
        self.assertIn(' 6 ', string)

    def testAliasJeff(self):
        string = self.bot.getRankText('jeff')
        self.assertIn('jeffispro ', string)
        self.assertIn(' 16033 ', string)
        self.assertIn(' 6 ', string)

    def testAlias_jeffispro(self):
        string = self.bot.getRankText('jeffispro')
        self.assertIn('jeffispro ', string)
        self.assertIn(' 16033 ', string)
        self.assertIn(' 6 ', string)


if __name__ == '__main__':
    from dotenv import load_dotenv, dotenv_values
    load_dotenv('.test-env')
    unittest.main()
