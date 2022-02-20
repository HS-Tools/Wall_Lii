import json

import requests

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
}


def filterText(text):
    text = text.replace("<b>", "")
    text = text.replace("</b>", "")
    text = text.replace("[x]", "")
    text = text.replace("\n", " ")
    text = text.replace("\xa0", " ")
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
    # dictionary to hold hero names and their ID's
    battlegrounds_heroes = {}
    # Variable of the final dictionary
    battlegrounds_heroes_buddies = {}

    # Read through all the data and find the hero names and their ID's
    for i in range(len(data_json)):
        if "battlegroundsHero" in data_json[i].keys():
            battlegrounds_heroes[data_json[i]["name"]] = data_json[i]["id"]

    # Loop through all the heroes in the dictionary and find their buddies
    for key in battlegrounds_heroes:
        for j in range(len(data_json)):
            if "isBattlegroundsBuddy" in data_json[j].keys():
                if data_json[j]["id"] == battlegrounds_heroes[key] + "_Buddy":
                    data = data_json[j]
                    buddy_string = f"{data['name']} is a Tier {data['techLevel']} {data['attack']}/{data['health']}. Ability: {filterText(data['text'])}"
                    battlegrounds_heroes_buddies[get_shortened_name(key)] = (
                        key,
                        buddy_string,
                    )
                elif data_json[j]["id"] == battlegrounds_heroes[key] + "_Buddy_G":
                    data = data_json[j]
                    golden_buddy_string = f"Golden {data['name']} is a Tier {data['techLevel']} {data['attack']}/{data['health']}. Ability: {filterText(data['text'])}"
                    battlegrounds_heroes_buddies[
                        get_shortened_name(key)
                    ] = battlegrounds_heroes_buddies[get_shortened_name(key)] + (
                        golden_buddy_string,
                    )

    return battlegrounds_heroes_buddies
