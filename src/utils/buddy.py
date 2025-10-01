# buddy_utils.py
from .buddies import easter_egg_buddies_dict
from .buddy_fetch import get_buddy_dict, get_trinkets_dict, parse_buddy, parse_trinket

# Initialize dictionaries once
buddy_dict = get_buddy_dict()
trinket_dict = get_trinkets_dict()

def update_buddy_dict_and_trinket_dict():
    global buddy_dict, trinket_dict
    buddy_dict = get_buddy_dict()
    trinket_dict = get_trinkets_dict()

def get_buddy_text(name: str):
    results = parse_buddy(name.lower(), buddy_dict, easter_egg_buddies_dict)
    return results if results else None


def get_trinket_text(name: str):
    return parse_trinket(name.lower(), trinket_dict)


def get_buddy_gold_tier_message(tier: str) -> str:
    tiers = {
        "1": [11, 13],
        "2": [13, 15],
        "3": [15, 17],
        "4": [17, 19],
        "5": [19, 21],
        "6": [21, 23],
    }
    if tier in tiers:
        initial, reset = tiers[tier]
        return f"A tier {tier} buddy has an initial cost of {initial} and a reset cost of {reset}"
    return "Invalid tier, try a number between 1 and 6 like !buddygold 3"
