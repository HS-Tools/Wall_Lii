import sys
import os
sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import data
from api import getLeaderboardSnapshot
from boto3.dynamodb.conditions import Key, Attr
from test import setup_production_environment
import unittest

class testLeaderboardGet(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls, fill server with data from season 2 which shouldn't change
        url = "http://localhost:8000"
        if 'ENDPOINT_URL' in os.environ.keys():
            url = os.environ['ENDPOINT_URL']

        self.database = data.RankingDatabaseClient( endpoint_url=url )
        setup_production_environment(self.database, url)
        tables = [table.name for table in self.database.resource.tables.all()]

        if 'fake-table-1' in tables:
            self.database.client.delete_table(TableName = 'fake-table-1')


    def setUp(self):
        self.table = self.database.create_table('fake-table-1')

    def tearDown(self):
        self.database.client.delete_table(TableName = 'fake-table-1')


    def testCreateTable(self):
        pass

    def testPutItem(self):
        self.database.put_item(region='NA',player='nina',rating=1,rank=1,lastUpdate=1)
        foo = self.database.get_item(region='NA', player='nina')
        self.assertEqual('nina', foo['PlayerName'])

    def testRankScan1(self):
        self.database.put_item(region='NA',player='nina',rating=1,rank=1,lastUpdate=1)
        foo = self.database.table.scan(
            FilterExpression= Attr('Rank').eq(1),
        )
        self.assertEqual(1, len(foo['Items']))

    def testRankScan2(self):
        self.database.put_item(region='NA',player='nina',rating=1,rank=1,lastUpdate=1)
        self.database.put_item(region='NA',player='lii',rating=1,rank=2,lastUpdate=1)
        foo = self.database.table.scan(
            FilterExpression= Attr('Rank').eq(1),
        )
        self.assertEqual(1, len(foo['Items']))

    def testRankScanNoResult(self):
        self.database.put_item(region='NA',player='nina',rating=1,rank=1,lastUpdate=1)
        self.database.put_item(region='NA',player='lii',rating=1,rank=2,lastUpdate=1)
        foo = self.database.table.scan(
            FilterExpression= Attr('Rank').eq(200),
        )
        self.assertEqual(0, len(foo['Items']))

    def testRankScan9(self):
        self.database.put_item(region='NA',player='nina',rating=1,rank=1,lastUpdate=1)
        for i in range(2,8):
            self.database.put_item(region='NA',player=str(i),rating=1,rank=i,lastUpdate=1)
        foo = self.database.table.scan(
            FilterExpression= Attr('Rank').eq(1),
        )
        self.assertEqual(1, len(foo['Items']))



if __name__ == '__main__':
    from dotenv import load_dotenv, dotenv_values
    load_dotenv('.test-env')
    unittest.main()
