import sys
import time

sys.path.append("../lambda-loader/src")
import unittest

from api import getLeaderboardSnapshot


class apiTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls
        self.ratingsDict, self.lastUpdated, self.season = getLeaderboardSnapshot(
            ["US"], "BG", 1, verbose=False
        )

    def testTime(self):
        """
        Test the last updated time
        """
        return  # test died because the leaderboards no longer provide time
        self.assertEqual("2020-12-15 21:03:43.669292317", self.lastUpdated["US"])

    def testNumAccounts(self):
        """
        There should be 200 accounts found
        """
        self.assertEqual(200, len(self.ratingsDict["US"]))

    def testAccount1(self):
        """
        There should be 200 accounts found
        """
        key = "saphirexx"
        self.assertTrue(key in self.ratingsDict["US"].keys())
        self.assertEqual(1, self.ratingsDict["US"][key]["rank"])
        self.assertEqual(22483, self.ratingsDict["US"][key]["rating"])

    def testGet500(self):
        """
        We can now get as many pages as we want
        """

        start = time.time()
        ratingsDict, lastUpdated, season = getLeaderboardSnapshot(
            ["US", "EU", "AP"], "BG", 1, verbose=False, total_count=500
        )
        end = time.time()
        print("to get 500 players from 3 leaderboards took", end - start, "seconds")

    def testGet5000(self):
        """
        We can now get as many pages as we want
        """

        start = time.time()
        ratingsDict, lastUpdated, season = getLeaderboardSnapshot(
            ["US", "EU", "AP"], "BG", 1, verbose=False, total_count=5000
        )
        end = time.time()
        print("to get 5000 players from 3 leaderboards took", end - start, "seconds")


if __name__ == "__main__":
    unittest.main()
