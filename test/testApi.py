import sys
sys.path.append("../lambda-loader/src")
from api import getLeaderboardSnapshot
import unittest

class apiTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls
        self.ratingsDict, self.lastUpdated, self.season = getLeaderboardSnapshot(['US'],'BG',1,verbose=False)

    def testTime(self):
        """
        Test the last updated time
        """
        self.assertEqual('2020-12-15 21:03:43.669292317', self.lastUpdated['US'])

    def testNumAccounts(self):
        """
        There should be 200 accounts found
        """
        self.assertEqual(200, len(self.ratingsDict['US']))

    def testAccount1(self):
        """
        There should be 200 accounts found
        """
        key = 'saphirexx'
        self.assertTrue(key in self.ratingsDict['US'].keys())
        self.assertEqual(1, self.ratingsDict['US'][key]['rank'])
        self.assertEqual(22483, self.ratingsDict['US'][key]['rating'])


if __name__ == '__main__':
    unittest.main()