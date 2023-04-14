import json

import requests
from fuzzywuzzy import process as fuzzysearch

url = "https://api.hearthstonejson.com/v1/latest/enUS/cards.json"
response = requests.get(url)
data_json = json.loads(response.text)

difficult_shortened_names = {
    "Death Speaker Blackthorn": "blackthorn",
    "Trade Prince Gallywix": "gallywix",
    "The Rat King": "ratking",
    "The Great Akazamzarak": "akazamzarak",
    "A. F. Kay": "afk",
    "The Lich King": "lichking",
    "Lich Baz'hial": "lichb",
    "Yogg-Saron, Hope's End": "yogg",
    "Forest Warden Omu": "omu",
    "Mr. Bigglesworth": "cat",
    "Heistbaron Togwaggle": "togwaggle",
}


def filterText(text):
    text = text.replace("<b>", "")
    text = text.replace("</b>", "")
    text = text.replace("[x]", "")
    text = text.replace("\n", " ")
    text = text.replace("\xa0", " ")
    text = text.replace("<i>( (turn, turns) left!)</i>", "")
    text = text.replace("<i>(", "")
    text = text.replace(")</i>", "")
    return text


def get_shortened_name(full_hero_name):
    name_words = full_hero_name.split(" ")

    titles = [
        "Lord",
        "Dancin'",
        "King",
        "Queen",
        "Fungalmancer",
        "Arch-Villain",
        "Captain",
        "Skycap'n",
        "Overlord",
        "Infinite",
        "Dinotamer",
        "Sir",
        "Sire",
        "The",
    ]

    if full_hero_name in difficult_shortened_names.keys():
        return difficult_shortened_names[full_hero_name]

    if name_words[0] not in titles:
        first_word = name_words[0]
    else:
        first_word = name_words[1]

    return "".join(c.lower() for c in first_word if c.isalnum())


def get_buddy_dict():
    # dictionary to hold hero ID's and their names
    _heroes = {}
    # Variable of the final dictionary
    buddies = {}

    # Loop through the heroes in data_json, and find their ID's and names
    for hero in filter(lambda card: "battlegroundsBuddyDbfId" in card, data_json):
        id_words = hero["id"].split("_")
        # verify that the card is not a skin
        if len(id_words) >= 2 and id_words[-2] == "HERO" and id_words[-1].isnumeric():
            _heroes[hero["id"]] = hero["name"]

    # Loop through the buddies in data_json and find their heroes
    for buddy in filter(lambda card: "isBattlegroundsBuddy" in card, data_json):
        # examples of `buddy["id"]`: "TB_BaconShop_HERO_93_Buddy", "TB_BaconShop_HERO_93_Buddy_G"
        hero_id, _buddy_is_golden = buddy["id"].split("_Buddy")
        buddy_is_golden = bool(_buddy_is_golden)

        if hero_id in _heroes:
            b = buddy
            buddy_string = f"{b['name']} is a Tier {b['techLevel']} {b['attack']}/{b['health']}. Ability: {filterText(b['text'])}"
            if not buddy_is_golden:
                buddies[get_shortened_name(_heroes[hero_id])] = (
                    _heroes[hero_id],
                    buddy_string,
                )
            else:
                golden_buddy_string = "Golden " + buddy_string
                buddies[get_shortened_name(_heroes[hero_id])] += (golden_buddy_string,)

    return buddies


def parse_buddy(name, buddies={}, eggs={}):
    if name in eggs:
        return eggs[name]

    elif name in buddies:
        return buddies[name]

    else:
        buddyOptions = list(buddies.keys())
        goodScores = fuzzysearch.extractBests(
            query=name, choices=buddyOptions, score_cutoff=65, limit=3
        )
        for name_scored, ratio_scored in goodScores:
            if ratio_scored >= 85:
                return buddies[name_scored]

        if len(goodScores) > 0:
            ## create a fake entry for no valid hero
            goodScoresNames = " or ".join(
                list(name_scored for name_scored, ratio_scored in goodScores)
            )
            return (
                None,
                f"{name} is not a valid hero, try again with {goodScoresNames}",
                f"{name} is not a valid hero, try again with {goodScoresNames}",
            )

        else:
            return (
                None,
                f"{name} is not a valid hero, try the name of the hero with no spaces or non alphabetic characters",
                f"{name} is not a valid hero,try the name of the hero with no spaces or non alphabetic characters",
            )
