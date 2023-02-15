import os
from datetime import datetime

import aiocron
import discord
from discord import option
from dotenv import load_dotenv
from pytz import timezone, utc

from buddies import easter_egg_buddies_dict
from buddy_fetch import get_buddy_dict, parse_buddy
from leaderboardBot import LeaderBoardBot
from parseRegion import isRegion

load_dotenv()

bot = discord.Bot()

channelIds = {
    "wall_lii": 811468284394209300,
    "wall-lii-requests": 846867129834930207,
    "test": 730782280674443327,
}

liiDiscordId = 204806965585510400

emotes = ["liiHappyCat", "liiCat", "ninaisFEESH", "liiWait"]


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.slash_command(guild_ids=[729524538559430670])
async def hello(ctx):
    await ctx.respond("Hello!")


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
    await ctx.respond(embed=getEmbedObject(response, args[0], name))


@bot.slash_command(guild_ids=[729524538559430670], description="Get a hero's buddy")
@option("buddy_name", description="Enter the buddy name")
async def buddy(ctx: discord.ApplicationContext, buddy_name: str):
    results = parse_buddy(buddy_name, buddyDict, easter_egg_buddies_dict)

    if results and results[0] is not None:
        embed = discord.Embed(
            title=f"{results[0]}'s buddy",
            description=results[1],
        )
        await ctx.respond(embed=embed)
    else:
        await ctx.respond("Buddy not found")


@bot.slash_command(
    guild_ids=[729524538559430670], description="Get a hero's golden buddy"
)
@option("golden_buddy_name", description="Enter the golden buddy name")
async def goldenbuddy(ctx: discord.ApplicationContext, golden_buddy_name: str):
    results = parse_buddy(golden_buddy_name, buddyDict, easter_egg_buddies_dict)

    if results and results[0] is not None:
        embed = discord.Embed(
            title=f"{results[0]}'s golden buddy",
            description=results[2],
        )
        await ctx.respond(embed=embed)


@bot.slash_command(guild_ids=[729524538559430670], description="Get a player's rank")
@option("player_name", description="Enter the player's name or rank")
@option("region", description="Enter the player's region", default="")
async def bgrank(ctx: discord.ApplicationContext, player_name: str, region: str):
    args = leaderboardBot.parseArgs("lii", player_name, region)
    await call(ctx, leaderboardBot.getRankText, "rank", *args)


@bot.slash_command(
    guild_ids=[729524538559430670], description="Get a player's record from today"
)
@option("player_name", description="Enter the player's name or rank")
@option("region", description="Enter the player's region", default="")
async def bgdaily(ctx: discord.ApplicationContext, player_name: str, region: str):
    args = leaderboardBot.parseArgs("lii", player_name, region)
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", *args)


@bot.slash_command(
    guild_ids=[729524538559430670], description="Get a player's record from yesterday"
)
@option("player_name", description="Enter the player's name or rank")
@option("region", description="Enter the player's region", default="")
async def yesterday(ctx: discord.ApplicationContext, player_name: str, region: str):
    args = leaderboardBot.parseArgs("lii", player_name, region)
    args.append(True)
    await call(ctx, leaderboardBot.getDailyStatsText, "yesterday", *args)


@bot.slash_command(
    guild_ids=[729524538559430670], description="Get Liisus's record from today"
)
async def bgdailii(ctx: discord.ApplicationContext):
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", "lii")


@bot.slash_command(
    guild_ids=[729524538559430670], description="Tell wall_lii he's a good boy"
)
async def goodbot(ctx: discord.ApplicationContext):
    await ctx.respond(":robot: Just doing my job :robot:")


@bot.slash_command(
    guild_ids=[729524538559430670], description="Map alias to player_name"
)
@option("alias", description="Enter the alias you'd like to use")
@option(
    "player_name", description="Enter the player name you'd like the alias to map to"
)
async def addalias(ctx: discord.ApplicationContext, alias: str, player_name: str):
    alias = alias.lower()
    name = player_name.lower()

    leaderboardBot.addAlias(alias, name)
    leaderboardBot.updateAlias()
    if alias in leaderboardBot.alias.keys() and leaderboardBot.alias[alias] == name:
        await ctx.respond(f"{alias} is now an alias for {name}")
    else:
        await ctx.respond(f"failed to set alias {alias} to name {name}")


@bot.slash_command(guild_ids=[729524538559430670], description="Remove an alias")
@option("alias", description="Enter the alias you'd like to use")
async def deletealias(ctx: discord.ApplicationContext, alias: str):
    alias = alias.lower()

    leaderboardBot.deleteAlias(alias)
    leaderboardBot.updateAlias()

    await ctx.respond(f"{alias} alias was deleted")


@bot.slash_command(
    guild_ids=[729524538559430670], description="Map alias to player_name"
)
@option("channel_name", description="Enter the channel you'd like to add wall_lii to")
@option(
    "player_name",
    description="Enter the player name of the streamer if it's different to the twitch name",
    default="",
)
async def addchannel(ctx, channel_name: str, player_name: str):
    channel_name = channel_name.lower()
    player_name = player_name.lower() if player_name != "" else channel_name

    leaderboardBot.addChannel(channel_name, player_name)

    await ctx.respond(
        f"{channel_name} will have wall_lii added to it with the default name of {player_name}"
    )


@bot.slash_command(
    guild_ids=[729524538559430670], description="Remove wall_lii from a twitch channel"
)
@option(
    "channel_name", description="Enter the channel you'd like to delete wall_lii from"
)
async def deletechannel(ctx, channel_name: str):
    channel = channel_name.lower()

    leaderboardBot.deleteChannel(channel)

    await ctx.respond(f"{channel} will have wall_lii removed")


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

    embed = discord.Embed(
        title=f"Daily Liiderboards for {get_pst_time()}", description=text
    )

    dedicated_channel_id = channelIds["wall_lii"]
    await bot.get_channel(int(dedicated_channel_id)).send(embed=embed)


@aiocron.crontab("59 6 * * *")
async def send_top16_daily_recap():
    embed = generateTop16Embed()
    dedicated_channel_id = channelIds["wall_lii"]
    await bot.get_channel(int(dedicated_channel_id)).send(embed=embed)


@bot.slash_command(
    guild_ids=[729524538559430670],
    description="Get the top 16 players from all regions",
)
async def top16(ctx):
    embed = generateTop16Embed()
    await ctx.respond(embed=embed)


@bot.slash_command(
    guild_ids=[729524538559430670],
    description="Secret test command for lii",
)
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

    dedicated_channel_id = channelIds["test"]
    await bot.get_channel(int(dedicated_channel_id)).send(embed=embed)


def get_pst_time():
    date_format = "%m-%d"
    date = datetime.now(tz=utc)
    date = date.astimezone(timezone("US/Pacific"))
    ptDateTime = date.strftime(date_format)
    return ptDateTime


def generateTop16Embed():
    top16_players_in_each_region = leaderboardBot.get_leaderboard_range(1, 16)

    embed = discord.Embed(
        title=f"Daily Top 16 Leaderboards @ {get_pst_time()}",
    )

    for region in top16_players_in_each_region.keys():
        valueString = ""
        for rank, rating, player in top16_players_in_each_region[region]:
            valueString += f"{rank}. **{player}** with **{rating}** MMR.\n"

        embed.add_field(name=region, value=valueString, inline=True)

    return embed


if __name__ == "__main__":
    leaderboardBot = LeaderBoardBot()
    buddyDict = get_buddy_dict()
    bot.run(os.environ["DISCORD_TOKEN"])
