import os
from datetime import datetime

import aiocron
import interactions
from dotenv import load_dotenv
from pytz import timezone, utc

from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict, parse_buddy
from leaderboardBot import LeaderBoardBot
from parseRegion import isRegion

load_dotenv()

channelIds = {
    "wall_lii": 811468284394209300,
    "wall-lii-requests": 846867129834930207,
    "test": 730782280674443327,
}

liiDiscordId = 204806965585510400

bot = interactions.Client(
    token=os.environ["DISCORD_TOKEN"], 
    default_scope=liiDiscordId
)

emotes = ["liiHappyCat", "liiCat", "ninaisFEESH", "liiWait"]


def getEmbedObject(text, player, command):
    embed = interactions.Embed(title=f"{player}'s {command}", description=text)
    return embed


def removeTwitchEmotes(s):
    for key in emotes:
        s = s.replace(key, "")
    return s


async def call(ctx, func, name, *args):
    response = removeTwitchEmotes(func(*args))
    await ctx.send(embed=getEmbedObject(response, args[0], name))


@bot.command(
    name="buddy",
    description="Get the buddy of a Hero",
    options = [
        interactions.Option(
            name="hero",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ],
)
async def buddy(ctx, hero):
    results = parse_buddy(hero, buddyDict, easter_egg_buddies_dict)

    if results and results[0] is not None:
        embed = interactions.Embed(
            title=f"{results[0]}'s buddy",
            description=results[1],
        )
        await ctx.send(embed=embed)


@bot.command(
    name="goldenbuddy",
    description="Get the golden buddy of a Hero",
    options = [
        interactions.Option(
            name="hero",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ],)
async def goldenbuddy(ctx, hero):
    results = parse_buddy(hero, buddyDict, easter_egg_buddies_dict)

    if results and results[0] is not None:
        embed = interactions.Embed(
            title=f"{results[0]}'s golden buddy",
            description=results[2],
        )
        await ctx.send(embed=embed)

@bot.command(
    options=[
        interactions.Option(
            name="player",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="rank",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="region",
            type=interactions.OptionType.STRING,
            required=False,
        ),
    ]
)
async def bgrank(ctx, *args):
    args = leaderboardBot.parseArgs("lii", *args)
    await call(ctx, leaderboardBot.getRankText, "rank", *args)
    # todo consider adding button to call bgdaily


@bot.command(
    options=[
        interactions.Option(
            name="player",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="rank",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="region",
            type=interactions.OptionType.STRING,
            required=False,
        ),
    ]
)
async def bgdaily(ctx, *args):
    args = leaderboardBot.parseArgs("lii", *args)
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", *args)


@bot.command(
    options=[
        interactions.Option(
            name="player",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="rank",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        interactions.Option(
            name="region",
            type=interactions.OptionType.STRING,
            required=False,
        ),
    ]
)
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


@bot.command(
    options=[
        interactions.Option(
            name="alias",
            type=interactions.OptionType.STRING,
            required=True,
        ),
        interactions.Option(
            name="playerName",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ])
async def addalias(ctx, alias, name):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        alias = alias.lower()
        name = name.lower()

        leaderboardBot.addAlias(alias, name)
        leaderboardBot.updateAlias()
        if (
            alias in leaderboardBot.alias.keys()
            and leaderboardBot.alias[alias] == name
        ):
            await ctx.send(f"{alias} is now an alias for {name}")
        else:
            await ctx.send(f"failed to set alias {alias} to name {name}")


@bot.command(
    options=[
        interactions.Option(
            name="alias",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ]
)
async def deletealias(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):

        if ctx.message.author.id == liiDiscordId:
            alias = args[0].lower()
            leaderboardBot.deleteAlias(alias)
            leaderboardBot.updateAlias()
            await ctx.send(f"{alias} alias was deleted")
        else:
            await ctx.send("Only Lii can delete aliases")


@bot.command(
    options=[
        interactions.Option(
            name="twitchChannel",
            type=interactions.OptionType.STRING,
            required=True,
        ),
        interactions.Option(
            name="playerName",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ]
)
async def addchannel(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        channelName = args[0].lower()
        playerName = args[1].lower() if len(args) > 1 else args[0].lower()

        leaderboardBot.addChannel(channelName, playerName)

        await ctx.send(
            f"{channelName} will have wall_lii added to it with the default name of {playerName}"
        )


@bot.command(
    options=[
        interactions.Option(
            name="twitchChannel",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ]
)
async def deletechannel(ctx, *args):
    if (
        ctx.message.channel.id == channelIds["wall-lii-requests"]
        or ctx.message.channel.id == channelIds["test"]
    ):
        if ctx.message.author.id == liiDiscordId:
            channel = args[0].lower()
            leaderboardBot.deleteChannel(channel)
            await ctx.send(f"{channel} channel was removed from the list")
        else:
            await ctx.send("Only Lii can remove wall_lii from channels")


# PI is on UTC time it seems
@aiocron.crontab("59 6 * * *")
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

    embed = interactions.Embed(
        title=f"Daily Liiderboards for {get_pst_time()}", description=text
    )

    dedicated_channel = bot.get_channel(channelIds["wall_lii"])
    recap = await dedicated_channel.send(embed=embed)
    await recap.pin()


@aiocron.crontab("59 6 * * *")
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

    embed = interactions.Embed(
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

    embed = interactions.Embed(
        title=f"Daily Top 16 Leaderboards @ {get_pst_time()}",
    )

    for region in top16_players_in_each_region.keys():
        valueString = ""
        for rank, rating, player in top16_players_in_each_region[region]:
            valueString += f"{rank}. **{player}** with **{rating}** MMR.\n"

        embed.add_field(name=region, value=valueString, inline=True)

    return embed


def removeSquareBrackets(args):
    newArgs = []

    for arg in args:
        newArg = arg.lstrip("[")
        newArg = newArg.rstrip("]")
        newArgs.append(newArg)

    return newArgs


if __name__ == "__main__":
    leaderboardBot = LeaderBoardBot()
    buddyDict = get_buddy_dict()

    bot.start()
