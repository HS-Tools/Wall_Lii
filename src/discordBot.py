import os
from datetime import datetime

import aiocron
import discord
from discord.ext import commands
from dotenv import load_dotenv
from fuzzywuzzy import process
from pytz import timezone, utc

from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict
from leaderboardBot import LeaderBoardBot
from parseRegion import isRegion

load_dotenv()

bot = commands.Bot(command_prefix="!")

channelIds = {
    "wall_lii": 811468284394209300,
    "wall-lii-requests": 846867129834930207,
    "test": 730782280674443327,
}

liiDiscordId = 204806965585510400

emotes = ["liiHappyCat", "liiCat", "ninaisFEESH", "liiWait"]


def getEmbedObject(text, player, command):
    embed = discord.Embed(title=f"{player}'s {command}", description=text)

    return embed


def removeTwitchEmotes(s):
    for key in emotes:
        s = s.replace(key, "")
    return s


async def call(ctx, func, name, *args):
    response = removeTwitchEmotes(func(*args))
    if len(args) >= 2:
        if not isRegion(args[1]):
            response = "Invalid region provided.\n" + response

    message = ctx.message
    try:
        await message.delete()
    except:
        pass
    await ctx.send(embed=getEmbedObject(response, args[0], name))


@bot.command()
async def buddy(ctx, *args):
    if len(args) < 1:
        await ctx.send("Insert a hero name after !buddy to use this command")
        return

    buddyName = args[0].lower()
    try:
        await ctx.message.delete()
    except:
        pass

    if buddyName in easter_egg_buddies_dict.keys():
        embed = discord.Embed(
            title=f"{easter_egg_buddies_dict[buddyName][0]}'s buddy",
            description=easter_egg_buddies_dict[buddyName][1],
        )
        await ctx.send(embed=embed)
        return

    if buddyName not in buddyDict.keys():
        buddyOptions = list(buddyDict.keys())
        goodScores = process.extractBests(
            query=buddyName, choices=buddyOptions, score_cutoff=65, limit=3
        )
        if len(goodScores) > 0:
            goodScoresNames = " or ".join(list(rate[0] for rate in goodScores))
            await ctx.send(
                "{} is not a valid hero, try again with {}".format(
                    buddyName, goodScoresNames
                )
            )
        else:
            await ctx.send(
                "{} is not a valid hero, try the name of the hero with no spaces or non alphabetic characters".format(
                    buddyName
                )
            )
    else:
        embed = discord.Embed(
            title=f"{buddyDict[buddyName][0]}'s buddy",
            description=buddyDict[buddyName][1],
        )
        await ctx.send(embed=embed)


@bot.command()
async def goldenbuddy(ctx, *args):
    if len(args) < 1:
        await ctx.send("Insert a hero name after !goldenbuddy to use this command")
        return

    buddyName = args[0].lower()
    try:
        await ctx.message.delete()
    except:
        pass

    if buddyName in easter_egg_buddies_dict.keys():
        embed = discord.Embed(
            title=f"{easter_egg_buddies_dict[buddyName][0]}'s golden buddy",
            description=easter_egg_buddies_dict[buddyName][2],
        )
        await ctx.send(embed=embed)
        return

    if buddyName not in buddyDict.keys():
        buddyOptions = list(buddyDict.keys())
        goodScores = process.extractBests(
            query=buddyName, choices=buddyOptions, score_cutoff=65, limit=3
        )
        if len(goodScores) > 0:
            goodScoresNames = " or ".join(list(rate[0] for rate in goodScores))
            await ctx.send(
                "{} is not a valid hero, try again with {}".format(
                    buddyName, goodScoresNames
                )
            )
        else:
            await ctx.send(
                "{} is not a valid hero, try the name of the hero with no spaces or non alphabetic characters".format(
                    buddyName
                )
            )
    else:
        embed = discord.Embed(
            title=f"{buddyDict[buddyName][0]}'s golden buddy",
            description=buddyDict[buddyName][2],
        )
        await ctx.send(embed=embed)


@bot.command()
async def bgrank(ctx, *args):
    args = leaderboardBot.parseArgs("lii", *args)
    await call(ctx, leaderboardBot.getRankText, "rank", *args)


@bot.command()
async def bgdaily(ctx, *args):
    args = leaderboardBot.parseArgs("lii", *args)
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", *args)


@bot.command()
async def yesterday(ctx, *args):
    args = leaderboardBot.parseArgs("lii", *args)
    args.append(True)  ## send the yesterday value to the function
    await call(ctx, leaderboardBot.getDailyStatsText, "yesterday", *args)


@bot.command()
async def bgdailii(ctx):
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", "lii")


@bot.command()
async def goodbot(ctx):
    await ctx.send(":robot: Just doing my job :robot:")


@bot.command()
async def addalias(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        message = ctx.message
        await message.delete()

        if len(args) < 2:
            await ctx.send("The command must have two words. !addalias [alias] [name]")
        else:
            alias = args[0].lower()
            name = args[1].lower()

            leaderboardBot.addAlias(alias, name)
            leaderboardBot.updateAlias()
            if (
                alias in leaderboardBot.alias.keys()
                and leaderboardBot.alias[alias] == name
            ):
                await ctx.send(f"{alias} is now an alias for {name}")
            else:
                await ctx.send(f"failed to set alias {alias} to name {name}")


@bot.command()
async def deletealias(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        message = ctx.message
        await message.delete()

        if ctx.message.author.id == liiDiscordId:
            if len(args) < 1:
                await ctx.send("The command must have one word. !deletealias [alias]")
            else:
                alias = args[0].lower()

                leaderboardBot.deleteAlias(alias)
                leaderboardBot.updateAlias()

                await ctx.send(f"{alias} alias was deleted")
        else:
            await ctx.send("Only Lii can delete aliases")


@bot.command()
async def addchannel(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        message = ctx.message
        await message.delete()

        if len(args) < 2:
            await ctx.send(
                "The command must have two words. !addchannel [channelName] [playerName]"
            )
        else:
            channelName = args[0].lower()
            playerName = args[1].lower()

            leaderboardBot.addChannel(channelName, playerName)

            await ctx.send(
                f"{channelName} will have wall_lii added to it with the default name of {playerName}"
            )


@bot.command()
async def deletechannel(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        message = ctx.message
        await message.delete()

        if ctx.message.author.id == liiDiscordId:
            if len(args) < 1:
                await ctx.send("The command must have one word. !deletechannel [alias]")
            else:
                channel = args[0].lower()

                leaderboardBot.deleteChannel(channel)

                await ctx.send(f"{channel} channel was removed from the list")
        else:
            await ctx.send("Only Lii can remove wall_lii from channels")


# PI is on UTC time it seems
@aiocron.crontab("59 7 * * *")
async def sendDailyRecap():
    climbers = leaderboardBot.getMostMMRChanged(5, True)
    losers = leaderboardBot.getMostMMRChanged(5, False)
    hardcore_gamers = leaderboardBot.getHardcoreGamers(5)
    highest_active = leaderboardBot.getHighestRatingAndActivePlayers(5)
    leaderboard_threshold = leaderboardBot.getLeaderboardThreshold()
    top16_threshold = leaderboardBot.getLeaderboardThreshold(16)

    climbersText = "**The top 5 climbers were:** \n"
    losersText = "**The top 5 unluckiest were:** \n"
    hardcore_gamersText = "**The top 5 grinders were:** \n"
    highestText = "**The top 5 highest rated active players were:** \n"
    threshholdText = "**The minimum rating to be on the leaderboards was: ** \n"
    top16Text = "**The minimum rating to be top 16 on the leaderboards was: ** \n"

    for index, climber in enumerate(climbers):
        climbersText += f"{index+1}. **{climber['Tag']}** climbed a total of **{climber['Change']}** from {climber['Start']} to {climber['End']} in the {climber['Region']} region \n"

    for index, loser in enumerate(losers):
        losersText += f"{index+1}. **{loser['Tag']}** lost a total of **{abs(loser['Change'])}** from {loser['Start']} to {loser['End']} in the {loser['Region']} region \n"

    for index, hardcore_gamer in enumerate(hardcore_gamers):
        hardcore_gamersText += f"{index+1}. **{hardcore_gamer['Tag']}** played a total of **{hardcore_gamer['Gamecount']}** games in the {hardcore_gamer['Region']} region \n"

    for index, highest in enumerate(highest_active):
        highestText += f"{index+1}. **{highest['Tag']}** went from **{highest['Start']}** to **{highest['End']}** in the {highest['Region']} region \n"

    for region, rating in leaderboard_threshold.items():
        threshholdText += f"{rating} in the {region} region \n"

    for region, rating in top16_threshold.items():
        top16Text += f"{rating} in the {region} region \n"

    text = (
        climbersText
        + "\n"
        + losersText
        + "\n"
        + hardcore_gamersText
        + "\n"
        + highestText
        + "\n"
        + threshholdText
        + "\n"
        + top16Text
    )

    embed = discord.Embed(
        title=f"Daily Liiderboards for {get_pst_time()}", description=text
    )

    dedicated_channel = bot.get_channel(channelIds["wall_lii"])
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()


@aiocron.crontab("59 7 * * *")
async def send_top16_daily_recap():
    embed = generateTop16Embed()
    dedicated_channel = bot.get_channel(channelIds["wall_lii"])
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()


@bot.command()
async def top16(ctx):
    embed = generateTop16Embed()

    message = ctx.message
    try:
        await message.delete()
    except:
        pass
    await ctx.send(embed=embed)


@aiocron.crontab("10 * * * *")  ## Every hour check for new buddies
async def check_for_new_buddies():
    global buddyDict
    temp_dict = get_buddy_dict()

    if temp_dict and len(temp_dict.keys()) > 0:
        buddyDict = temp_dict


@bot.command()
async def test(ctx):

    climbers = leaderboardBot.getMostMMRChanged(5, True)
    losers = leaderboardBot.getMostMMRChanged(5, False)
    hardcore_gamers = leaderboardBot.getHardcoreGamers(5)
    highest_active = leaderboardBot.getHighestRatingAndActivePlayers(5)
    leaderboard_threshold = leaderboardBot.getLeaderboardThreshold()
    top16_threshold = leaderboardBot.getLeaderboardThreshold(16)

    climbersText = "**The top 5 climbers were:** \n"
    losersText = "**The top 5 unluckiest were:** \n"
    hardcore_gamersText = "**The top 5 grinders were:** \n"
    highestText = "**The top 5 highest rated active players were:** \n"
    threshholdText = "**The minimum rating to be on the leaderboards was: ** \n"
    top16Text = "**The minimum rating to be top 16 on the leaderboards was: ** \n"

    for index, climber in enumerate(climbers):
        climbersText += f"{index+1}. **{climber['Tag']}** climbed a total of **{climber['Change']}** from {climber['Start']} to {climber['End']} in the {climber['Region']} region \n"

    for index, loser in enumerate(losers):
        losersText += f"{index+1}. **{loser['Tag']}** lost a total of **{abs(loser['Change'])}** from {loser['Start']} to {loser['End']} in the {loser['Region']} region \n"

    for index, hardcore_gamer in enumerate(hardcore_gamers):
        hardcore_gamersText += f"{index+1}. **{hardcore_gamer['Tag']}** played a total of **{hardcore_gamer['Gamecount']}** games in the {hardcore_gamer['Region']} region \n"

    for index, highest in enumerate(highest_active):
        highestText += f"{index+1}. **{highest['Tag']}** went from **{highest['Start']}** to **{highest['End']}** in the {highest['Region']} region \n"

    for region, rating in leaderboard_threshold.items():
        threshholdText += f"{rating} in the {region} region \n"

    for region, rating in top16_threshold.items():
        top16Text += f"{rating} in the {region} region \n"

    text = (
        climbersText
        + "\n"
        + losersText
        + "\n"
        + hardcore_gamersText
        + "\n"
        + highestText
        + "\n"
        + threshholdText
        + "\n"
        + top16Text
    )

    embed = discord.Embed(
        title=f"Daily Liiderboards for {get_pst_time()}", description=text
    )

    dedicated_channel = bot.get_channel(channelIds["test"])
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()


def get_pst_time():
    date_format = "%m-%d"
    date = datetime.now(tz=utc)
    date = date.astimezone(timezone("US/Pacific"))
    ptDateTime = date.strftime(date_format)
    return ptDateTime


def generateTop16Embed():
    top16_players_in_each_region = leaderboardBot.get_leaderboard_range(1, 16)

    discord_payload = ""

    def append_to_discord_payload(string, payload):
        payload += string
        payload += "\n"
        return payload

    for region in top16_players_in_each_region.keys():
        discord_payload = append_to_discord_payload(
            f"**{region} Top 16 **", discord_payload
        )
        for rank, rating, player in top16_players_in_each_region[region]:
            discord_payload = append_to_discord_payload(
                f"{rank}. **{player}** with **{rating}** MMR.", discord_payload
            )
        # Add a linebreak after each top 16.
        discord_payload += "\n"

    embed = discord.Embed(
        title=f"Daily Top 16 Leaderboards @ {get_pst_time()}",
        description=discord_payload,
    )

    return embed


if __name__ == "__main__":
    leaderboardBot = LeaderBoardBot()
    buddyDict = get_buddy_dict()

    bot.run(os.environ["DISCORD_TOKEN"])
