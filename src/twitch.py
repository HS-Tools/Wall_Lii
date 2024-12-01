import os

import aiocron
from dotenv import load_dotenv
from twitchio.ext import commands

from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict, get_trinkets_dict, parse_buddy, parse_trinket
from leaderboardBot import LeaderboardBot
from parseRegion import isRegion

# Override twitchio error functions to stop spam in logs

commands.Bot.event_command_error = None

load_dotenv()

leaderboardBot = LeaderboardBot()

initialChannels = leaderboardBot.getChannels()
greetingChannels = []
buddyDict = get_buddy_dict()
trinketDict = get_trinkets_dict()

helpString = "HeyGuys I'm a bot that checks the BG leaderboard. My commands are !bgrank [name], !bgdaily [name], !yesterday [name], !buddy [hero], !goldenbuddy [hero], !buddygold [tier] !bgpatch and !calendar"

twitchBot = commands.Bot(
    token=os.environ["TMI_TOKEN"],
    irc_token=os.environ["TMI_TOKEN"],
    client_id=os.environ["CLIENT_ID"],
    nick=os.environ["BOT_NICK"],
    prefix=os.environ["BOT_PREFIX"],
    initial_channels=[
        "liihs",
        # "jeefhs",
        # "rdulive",
        # "dogdog",
        # "xqn_thesad",
        # "matsuri_hs",
        # "zorgo_hs",
        # "sunbaconrelaxer",
        # "shadybunny",
        # "hapabear",
        # "sjow",
        # "bofur_hs",
        # "ixxdeee",
        # "wobbleweezy",
        # "awedragon",
        # "benice92",
        # "sevel07",
        # "zavadahs",
        # "pockyplays",
        # "terry_tsang_gaming",
        # "dreads",
        # "sunglitters",
        # "fasteddiehs",
        # "fritterus",
        # "bixentehs",
        # "beterbabbit",
        # "asmodaitv",
        # "jkirek_",
        # "harain",
        # "missbowers",
        # "educated_collins",
        # "gospodarlive",
        # "neflida",
        # "babofat",
        # "tume111",
        # "doudzo",
    ],
)


def parseArgs(ctx):
    default = initialChannels[ctx.channel.name]
    args = ctx.message.content.split(" ")[1:]
    return leaderboardBot.parseArgs(default, *args)


async def call(ctx, func, name, *args):
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!' TEST")
        return

    response = func(*args)
    if len(args) >= 2:
        if not isRegion(args[1]):
            response = "Invalid region provided.\n" + response

    await ctx.send(f"{response} TEST")


@twitchBot.command(name="buddy")
async def getBuddy(ctx):

    if ctx.channel.name == "dogdog":
        return

    if len(ctx.message.content.split(" ")) < 2:
        return

    buddyName = ctx.message.content.split(" ")[1].lower()

    results = parse_buddy(buddyName, buddyDict, easter_egg_buddies_dict)

    if results:
        await ctx.send(results[1])


@twitchBot.command(name="trinket")
async def getTrinket(ctx):
    if len(ctx.message.content.split(" ")) < 2:
        return

    trinketName = " ".join(ctx.message.content.split(" ")[1:]).lower()
    results = parse_trinket(trinketName, trinketDict)

    if results:
        await ctx.send(results)


@twitchBot.command(name="buddygold")
async def getBuddyGold(ctx):
    tiers = {
        1: [11, 13],
        2: [13, 15],
        3: [15, 17],
        4: [17, 19],
        5: [19, 21],
        6: [21, 23],
    }
    if len(ctx.message.content.split(" ")) < 2:
        await ctx.send("Add a tier between 1 and 6 like !buddygold 3")
    else:
        buddyTier = ctx.message.content.split(" ")[1]

        if str.isdigit(buddyTier) and int(buddyTier) <= 6 and int(buddyTier) >= 1:
            buddyTier = int(buddyTier)
            await ctx.send(
                f"A tier {buddyTier} buddy has an initial cost of {tiers[buddyTier][0]} \
                    and a reset cost of {tiers[buddyTier][1]}"
            )
        else:
            await ctx.send(
                "Invalid tier, try a number between 1 and 6 like !buddygold 3"
            )


@twitchBot.command(name="Shush")
async def getBuddy(ctx):
    await ctx.send("Shush")


@twitchBot.command(name="shush")
async def getBuddy(ctx):
    await ctx.send("Shush")


@twitchBot.command(name="curves")
async def getCurves(ctx):
    await ctx.send(
        "Check out www.BGcurvesheet.com for information about heros and curves"
    )


@twitchBot.command(name="Frog")
async def getFrog(ctx):
    await ctx.send("liiPers liiPers liiPers")


@twitchBot.command(name="frog")
async def getfrog(ctx):
    await ctx.send("liiPers liiPers liiPers")


@twitchBot.command(name="goldenbuddy")
async def getGoldenBuddy(ctx):
    if ctx.channel.name == "dogdog":
        return

    if len(ctx.message.content.split(" ")) < 2:
        return

    buddyName = ctx.message.content.split(" ")[1].lower()

    results = parse_buddy(buddyName, buddyDict, easter_egg_buddies_dict)

    if results:
        await ctx.send(results[2])


@twitchBot.command(name="gold")
async def getGold(ctx):
    incorrectUseText = (
        "Use this command with the number of gold your quest requires: !gold 55"
    )
    if len(ctx.message.content.split(" ")) < 2:
        await ctx.send(incorrectUseText)
        return

    try:
        goldAmount = int(ctx.message.content.split(" ")[1])
    except:
        await ctx.send(incorrectUseText)
        return

    # Will calculate turn quest will be completed based on startingTurn and goldAmount of quest.
    startingTurn = 1
    maxGold = 10
    currentGold = startingTurn + 2
    turn = startingTurn

    # Failsafe.
    if currentGold > maxGold:
        currentGold = maxGold

    while goldAmount > currentGold:
        goldAmount -= currentGold
        turn += 1
        if currentGold < maxGold:
            currentGold += 1

    if turn > startingTurn:
        await ctx.send(
            f"Turn {turn}, or Turn {turn - 1} if {goldAmount} extra gold is spent."
        )
    else:
        await ctx.send(f"Turn {turn}.")


@twitchBot.event()
async def event_message(msg):

    # make sure the bot ignores itself and the streamer
    if msg.echo:
        return

    if (
        msg.channel.name.lower() == "liihs"
        and msg.author.is_mod
        and msg.content.lower().find("mods assemble") != -1
    ):
        await msg.channel.send("MODS Assemble")


@twitchBot.command(name="bgrank")
async def getRank(ctx):
    args = parseArgs(ctx)
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!' TEST")
        return
    response = leaderboardBot.get_rank(*args)
    await ctx.send(f"{response} TEST")


@twitchBot.command(name="bgdaily")
async def getDailyStats(ctx):
    args = parseArgs(ctx)
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!' TEST")
        return
    response = leaderboardBot.get_daily_stats(*args)
    await ctx.send(f"{response} TEST")


@twitchBot.command(name="bgweekly")
async def getWeeklyStats(ctx):
    args = parseArgs(ctx)
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!' TEST")
        return
    response = leaderboardBot.get_weekly_stats(*args)
    await ctx.send(f"{response} TEST")


@twitchBot.command(name="tomorrow")
async def tomorrow(ctx):
    args = parseArgs(ctx)
    name = args[0]
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!' TEST")
        return
    await ctx.send(f"{name} will be rank 1 for sure liiYep TEST")


@twitchBot.command(name="patch")
async def patch(ctx):
    await ctx.send(leaderboardBot.patch_link)


@twitchBot.command(name="yesterday")
async def getYesterdayStats(ctx):
    args = parseArgs(ctx)
    args.append(True)  ## send the yesterday value to the function
    await call(ctx, leaderboardBot.getDailyStatsText, "yesterday", *args)


@twitchBot.command(name="bgdailii")
async def bgdailii(ctx):
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", "lii")


@twitchBot.command(name="goodbot")
async def goodBot(ctx):
    await ctx.send("MrDestructoid Just doing my job MrDestructoid")


@twitchBot.command(name="wall_lii")
async def wall_lii(ctx):
    await ctx.send(helpString)


@twitchBot.command(name="help")
async def help(ctx):
    await ctx.send(helpString)


@twitchBot.command(name="calendar")
async def calendar(ctx):
    await ctx.send(
        "Check out all the community tournaments for this month at HSBGClub.com/Calendar"
    )


@twitchBot.event()
async def event_join(channel, user):
    global greetingChannels
    if channel.name in greetingChannels:
        await channel.send(
            f"Hello @{channel.name}. I'm a bot that allows you to see leaderboard data for Hearthstone Battlegrounds. Type !help to see all my commands!"
        )
        greetingChannels.remove(channel.name)


@twitchBot.command(name="duorank")
async def duorank(ctx):
    """Get player info by rank or name for Duo mode"""
    args = parseArgs(ctx)
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!' TEST")
        return
    response = leaderboardBot.get_rank(*args, game_type="battlegroundsduo")
    await ctx.send(f"{response} TEST")


if __name__ == "__main__":
    print(f"Debug - Starting bot")
    twitchBot.run()
