import os
import sys

sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import unittest
from test import setup_production_environment

import data
from boto3.dynamodb.conditions import Attr, Key
from handler import add_leaderboards_to_db

from default_alias import alias as default_alias
from default_channels import channels as default_channels
from leaderboardBot import LeaderBoardBot

jeef = "not-another-freaking-jeeeeeeef-alias"


class testLeaderboardGet(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        ## do 1 poll from the server to minimize repeated api calls, fill server with data from season 2 which shouldn't change
        url = "http://localhost:8000"
        if "ENDPOINT_URL" in os.environ.keys():
            url = os.environ["ENDPOINT_URL"]

        self.database = data.RankingDatabaseClient(endpoint_url=url)
        setup_production_environment(self.database, url)
        tables = [table.name for table in self.database.resource.tables.all()]

        if "testLeaderboardBot" in tables:
            self.database.client.delete_table(TableName="testLeaderboardBot")

        self.database.create_table("testLeaderboardBot")
        add_leaderboards_to_db(self.database, ["US"], "BG", 1, False)

        self.bot = LeaderBoardBot(table_name="testLeaderboardBot", endpoint_url=url)
        self.bot.addDefaultAlias()
        self.bot.updateAlias()

        self.img = self.database.table.scan()

    @classmethod
    def tearDownClass(self):
        self.database.client.delete_table(TableName="testLeaderboardBot")

    def setUp(self):
        pass

    def tearDown(self):
        self.bot.updateAlias()
        if jeef in self.bot.alias:
            self.bot.deleteAlias(jeef)
            self.bot.updateAlias()
        if jeef in self.bot.getChannels():
            self.bot.channel_table.delete_item(Key={"ChannelName": jeef})

    def testGetPlayerData(self):
        items = self.bot.getPlayerData("saphirexx", self.bot.table)
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual("saphirexx", item["PlayerName"])
        self.assertEqual(1, item["Rank"])
        self.assertEqual(22483, item["Ratings"][0])

    def testGetRankNumData(self):
        items = self.bot.getEntryFromRank(1, "US")
        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual("saphirexx", item["PlayerName"])
        self.assertEqual(1, item["Rank"])
        self.assertEqual(22483, item["Ratings"][0])

    def testGetRankNumText(self):
        string = self.bot.getRankText("1", "US")
        self.assertIn("saphirexx ", string)
        self.assertIn(" 22483 ", string)
        self.assertIn(" 1 ", string)

    def testGetRankNumTextAlt(self):
        string = self.bot.getRankText("2", "NA")
        self.assertIn("mmrloophole ", string)
        self.assertIn(" 22019 ", string)
        self.assertIn(" 2 ", string)

    def testGetRankNumEgg(self):
        string = self.bot.getRankText("420", "NA")
        self.assertEqual("don't do drugs kids", string)

    def testGetRankText(self):
        string = self.bot.getRankText("saphirexx", "US")
        self.assertIn("saphirexx ", string)
        self.assertIn(" 22483 ", string)
        self.assertIn(" 1 ", string)

    def testGetRankTextAlt(self):
        string = self.bot.getRankText(*("MMRloophole", "NA"))
        self.assertIn("mmrloophole ", string)
        self.assertIn(" 22019 ", string)
        self.assertIn(" 2 ", string)

    def testGetRankTextNum(self):
        string = self.bot.getRankText("1", "US")
        self.assertIn("saphirexx ", string)
        self.assertIn(" 22483 ", string)
        self.assertIn(" 1 ", string)

    def testGetRankTextNoRegion(self):
        string = self.bot.getRankText("saphirexx")
        self.assertIn("saphirexx ", string)
        self.assertIn(" 22483 ", string)
        self.assertIn(" 1 ", string)

    def testGetReadableRegion(self):
        string = self.bot.getRankText("vaguerabbit", "US")
        self.assertIn("Americas ", string)

    def testParseArgDefault(self):
        args = self.bot.parseArgs("lii")
        self.assertEqual("lii", args[0])
        self.assertIsNone(args[1])

    def testParseArgName(self):
        args = self.bot.parseArgs(
            "lii",
            "quinnabr",
        )
        self.assertEqual("quinnabr", args[0])
        self.assertIsNone(args[1])

    def testParseArgRegion(self):
        args = self.bot.parseArgs(
            "lii",
            "EU",
        )
        self.assertEqual("lii", args[0])
        self.assertEqual("EU", args[1])

    def testParseArgUserRegion(self):
        args = self.bot.parseArgs(
            "lii",
            "quinnabr",
            "EU",
        )
        self.assertEqual("quinnabr", args[0])
        self.assertEqual("EU", args[1])

    def testParseArgRegionSwap(self):
        args = self.bot.parseArgs(
            "lii",
            "EU",
            "quinnabr",
        )
        self.assertEqual("quinnabr", args[0])
        self.assertEqual("EU", args[1])

    def testAliasJeef(self):
        string = self.bot.getRankText("jeef")
        self.assertIn("jeef ", string)
        self.assertIn(" 16033 ", string)
        self.assertIn(" 6 ", string)

    def testAliasJeff(self):
        string = self.bot.getRankText("jeff")
        self.assertIn("jeef ", string)
        self.assertIn(" 16033 ", string)
        self.assertIn(" 6 ", string)

    def testAlias_jeffispro(self):
        string = self.bot.getRankText("jeef")
        self.assertIn("jeef ", string)
        self.assertIn(" 16033 ", string)
        self.assertIn(" 6 ", string)

    def testAlias_add_jeeeeeeef(self):
        self.assertFalse(jeef in self.bot.alias.keys())
        self.bot.addAlias(jeef, "jeef")
        new = self.bot.getNewAlias()
        self.assertEqual("jeef", new[jeef])
        self.assertEqual(1 + len(default_alias), len(new))

    def testAlias_add_jeeeeeeef2(self):
        self.assertFalse(jeef in self.bot.alias.keys())
        self.bot.addAlias(jeef, "jeef")
        new = self.bot.getNewAlias()
        self.assertEqual("jeef", new[jeef])
        self.assertEqual(1 + len(default_alias), len(new))
        new = self.bot.getNewAlias()
        self.assertEqual("jeef", new[jeef])
        self.assertEqual(1 + len(default_alias), len(new))

    def testChannel_add_jeeeeeeef(self):
        self.assertFalse(jeef in self.bot.getChannels())
        self.bot.addChannel(jeef, "jeef")
        new = self.bot.getNewChannels()
        self.assertEqual("jeef", new[jeef])
        self.assertEqual(1, len(new))

    def testChannel_add_jeeeeeeef2(self):
        self.assertFalse(jeef in self.bot.getChannels())
        self.bot.addChannel(jeef, "jeef")
        new = self.bot.getNewChannels()
        self.assertEqual("jeef", new[jeef])
        self.assertEqual(1, len(new))
        new = self.bot.getNewChannels()
        self.assertEqual(0, len(new))

    def test_get_top16(self):
        top_16_data = self.bot.get_leaderboard_range(1, 16)
        for region in top_16_data.keys():
            assert len(top_16_data[region]) == 16
            player_name_set = set()
            rank_counter = 1
            previous_rating = float("inf")
            for rank, rating, name in top_16_data[region]:
                # Assert that all players in top 16 are unique.
                assert name not in player_name_set
                player_name_set.add(name)
                # Assert that ranks are descending 1->16
                assert rank == rank_counter
                rank_counter += 1
                # Assert that ratings are in descending order.
                assert rating <= previous_rating
                previous_rating = rating


if __name__ == "__main__":
    print(f"testing leaderboardBot")
    from dotenv import dotenv_values, load_dotenv

    load_dotenv(".test-env")
    unittest.main()
