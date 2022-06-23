import os

import aiocron
from dotenv import load_dotenv
from twitchio.ext import commands
from twitchio.ext.commands import CommandNotFound

from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict, parse_buddy
from leaderboardBot import LeaderBoardBot
from parseRegion import isRegion

load_dotenv()

leaderboardBot = LeaderBoardBot()

initialChannels = leaderboardBot.getChannels()
buddyDict = get_buddy_dict()

twitchBot = commands.Bot(
    token=os.environ["TMI_TOKEN"],
    irc_token=os.environ["TMI_TOKEN"],
    client_id=os.environ["CLIENT_ID"],
    nick=os.environ["BOT_NICK"],
    prefix=os.environ["BOT_PREFIX"],
    initial_channels=["liihs"],
)

# @twitchBot.event()
# async def event_command_error(error, data):
#     if type(data) == CommandNotFound:


def parseArgs(ctx):
    default = initialChannels[ctx.channel.name]
    args = ctx.message.content.split(" ")[1:]
    return leaderboardBot.parseArgs(default, *args)


async def call(ctx, func, name, *args):
    if args[0][0] == "!":
        await ctx.send("Names can't start with '!'")
        return

    response = func(*args)
    if len(args) >= 2:
        if not isRegion(args[1]):
            response = "Invalid region provided.\n" + response

    await ctx.send(response)


@twitchBot.command(name="buddy")
async def getBuddy(ctx):
    if len(ctx.message.content.split(" ")) < 2:
        return

    buddyName = ctx.message.content.split(" ")[1].lower()

    results = parse_buddy(buddyName, buddyDict, easter_egg_buddies_dict)

    if results:
        await ctx.send(results[1])


@twitchBot.command(name="Shush")
async def getBuddy(ctx):
    await ctx.send("Shush")


@twitchBot.command(name="shush")
async def getBuddy(ctx):
    await ctx.send("Shush")


@twitchBot.command(name="goldenbuddy")
async def getGoldenBuddy(ctx):
    if len(ctx.message.content.split(" ")) < 2:
        return

    buddyName = ctx.message.content.split(" ")[1].lower()

    results = parse_buddy(buddyName, buddyDict, easter_egg_buddies_dict)

    if results:
        await ctx.send(results[2])


@twitchBot.event
async def event_message(ctx):
    # make sure the bot ignores itself and the streamer
    if ctx.message.author.name.lower() == os.environ["BOT_NICK"].lower():
        return
    await twitchBot.handle_commands(ctx)


@twitchBot.command(name="bgrank")
async def getRank(ctx):
    if ctx.message.channel.name == "ixxdeee":
        return
    args = parseArgs(ctx)
    await call(ctx, leaderboardBot.getRankText, "rank", *args)


@twitchBot.command(name="bgdaily")
async def getDailyStats(ctx):
    args = parseArgs(ctx)
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", *args)


@twitchBot.command(name="tomorrow")
async def tomorrow(ctx):
    args = parseArgs(ctx)
    name = args[0]

    if args[0][0] == "!":
        await ctx.send("Names can't start with '!'")
        return

    await ctx.send(f"{name} will be rank 1 for sure liiYep")


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
    await ctx.send(
        "HeyGuys I'm a bot that checks the BG leaderboard to get data about player ranks and daily MMR fluctuations. I reset daily at Midnight CA time. Try using !bgrank [name] and !bgdaily [name] and !yesterday [name]."
    )


@twitchBot.command(name="help")
async def help(ctx):
    await ctx.send(
        "HeyGuys I'm a bot that checks the BG leaderboard to get data about player ranks and daily MMR fluctuations. I reset daily at Midnight CA time. Try using !bgrank [name] and !bgdaily [name] and !yesterday [name]."
    )


if __name__ == "__main__":

    @aiocron.crontab("* * * * *")  ## Every minute check for new channels
    async def updateChannels():
        global initialChannels

        channels = leaderboardBot.getChannels()

        joined_channels = list(map(lambda x: x.name, twitchBot.connected_channels))

        new_channels = []
        greeting_channels = []

        for channel in channels:
            if channel not in joined_channels:
                new_channels.append(channel)

                if channel not in initialChannels:
                    greeting_channels.append(channel)
                    initialChannels = leaderboardBot.getChannels()

            if len(new_channels) >= 50:
                break

        if len(new_channels) > 0:
            print("Joined these channels: " + str(new_channels))
        try:
            await twitchBot.join_channels(new_channels)
        except Exception as err:
            print(f"Joining error: ${err}")

        # Update initialChannels in case there's a change to the configuration of a channel's name
        initialChannels = leaderboardBot.getChannels()

        for channel_name in greeting_channels:
            channel = twitchBot.get_channel(channel_name)
            await channel.send(
                f"Hello @{channel_name} and @chat, I'm a bot that allows you to see leaderboard data for Hearthstone Battlegrounds. Type !help to see all my commands!"
            )

    @aiocron.crontab("* * * * *")  ## Every minute check for new alias
    async def updateAlias():
        leaderboardBot.getNewAlias()

    @aiocron.crontab("10 * * * *")  ## Every hour check for new buddies
    async def check_for_new_buddies():
        global buddyDict
        temp_dict = get_buddy_dict()

        if temp_dict and len(temp_dict.keys()) > 0:
            buddyDict = temp_dict

    twitchBot.run()
