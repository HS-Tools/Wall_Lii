import os
import sys

sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import unittest

from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict, parse_buddy


class testLeaderboardGet(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.eggs = easter_egg_buddies_dict
        self.buddies = get_buddy_dict()

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testFetch(self):
        assert "galewing" in self.buddies

    def testParse(self):
        result = parse_buddy("galewing", self.buddies, self.eggs)
        assert result[0] == "Galewing"
        assert "Flight Trainer" in result[1]
        assert "Flight Trainer" in result[2]

    def testParseNull(self):
        result = parse_buddy("galewing")
        assert result[0] is None
        assert "is not a valid hero" in result[1]
        assert "is not a valid hero" in result[2]

    def testParseGalewind(self):
        result = parse_buddy("galewind", self.buddies, self.eggs)
        assert result[0] == "Galewing"
        assert "Flight Trainer" in result[1]
        assert "Flight Trainer" in result[2]

    def testParseGalewand(self):
        result = parse_buddy("galewand", self.buddies, self.eggs)
        assert result[0] is None
        assert "galewing" in result[1]
        assert "galewing" in result[2]


if __name__ == "__main__":
    print(f"testing buddies")

    unittest.main()
