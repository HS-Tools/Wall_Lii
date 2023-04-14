import asyncio
import os
from datetime import datetime

import aiocron
import discord
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
frontpage_channel_id = 1096490528947851304
frontpage_message_id = 1096514937813217370

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
@discord.option("buddy_name", description="Enter the buddy name")
async def buddy(ctx: discord.ApplicationContext, buddy_name: str):
    results = parse_buddy(buddy_name, buddyDict, easter_egg_buddies_dict)

    await ctx.defer()
    asyncio.sleep(0.1)

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
@discord.option("golden_buddy_name", description="Enter the golden buddy name")
async def goldenbuddy(ctx: discord.ApplicationContext, golden_buddy_name: str):
    results = parse_buddy(golden_buddy_name, buddyDict, easter_egg_buddies_dict)

    await ctx.defer()
    asyncio.sleep(0.1)

    if results and results[0] is not None:
        embed = discord.Embed(
            title=f"{results[0]}'s golden buddy",
            description=results[2],
        )
        await ctx.respond(embed=embed)


@bot.slash_command(guild_ids=[729524538559430670], description="Get a player's rank")
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default="")
async def bgrank(ctx: discord.ApplicationContext, player_name: str, region: str):
    args = leaderboardBot.parseArgs("lii", player_name, region)
    await call(ctx, leaderboardBot.getRankText, "rank", *args)


@bot.slash_command(
    guild_ids=[729524538559430670], description="Get a player's record from today"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default="")
async def bgdaily(ctx: discord.ApplicationContext, player_name: str, region: str):
    args = leaderboardBot.parseArgs("lii", player_name, region)
    await call(ctx, leaderboardBot.getDailyStatsText, "daily", *args)


@bot.slash_command(
    guild_ids=[729524538559430670], description="Get a player's record from yesterday"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default="")
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
@discord.option("alias", description="Enter the alias you'd like to use")
@discord.option(
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
@discord.option("alias", description="Enter the alias you'd like to use")
async def deletealias(ctx: discord.ApplicationContext, alias: str):
    alias = alias.lower()

    leaderboardBot.deleteAlias(alias)
    leaderboardBot.updateAlias()

    await ctx.respond(f"{alias} alias was deleted")


@bot.slash_command(
    guild_ids=[729524538559430670], description="Map alias to player_name"
)
@discord.option(
    "channel_name", description="Enter the channel you'd like to add wall_lii to"
)
@discord.option(
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
@discord.option(
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


# @aiocron.crontab("59 7 * * *")
# async def send_top16_daily_recap():
#     embed = generateTop16Embed()
#     dedicated_channel_id = channelIds["wall_lii"]
#     await bot.get_channel(int(dedicated_channel_id)).send(embed=embed)


@aiocron.crontab("10 * * * *")  ## Every hour check for new buddies
async def check_for_new_buddies():
    global buddyDict
    temp_dict = get_buddy_dict()
    if temp_dict and len(temp_dict.keys()) > 0:
        buddyDict = temp_dict


@aiocron.crontab("* * * * *")
async def update_front_page():
    frontpage_channel = bot.get_channel(frontpage_channel_id)
    frontpage_message = await frontpage_channel.fetch_message(frontpage_message_id)
    await frontpage_message.edit(embed=generateTopXEmbed(25))


@bot.slash_command(
    guild_ids=[729524538559430670],
    description="Get the top 16 players from all regions",
)
async def top16(ctx):
    embed = generateTopXEmbed(16)
    await ctx.respond(embed=embed)


@bot.slash_command(
    guild_ids=[729524538559430670],
    description="Edit !bgpatch command on twitch for wall_lii",
)
@discord.option(
    "patch_link", description="Enter the channel you'd like to delete wall_lii from"
)
async def edit_bg_patch(ctx, patch_link: str):
    leaderboardBot.editPatchLink(patch_link)
    await ctx.respond(f"!bgpatch is now {patch_link}")


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
    date_format = "%m-%d %H:%M %Z"
    date = datetime.now(tz=utc)
    date = date.astimezone(timezone("US/Pacific"))
    ptDateTime = date.strftime(date_format)
    return ptDateTime


def generateTopXEmbed(num):
    topX_players_in_each_region = leaderboardBot.get_leaderboard_range(1, num)

    embed = discord.Embed(
        title=f"Top {num} Leaderboard for {get_pst_time()}",
    )

    for region in sorted(topX_players_in_each_region.keys(), reverse=True):
        valueString = ""
        for rank, rating, player, delta in topX_players_in_each_region[region]:
            if delta != 0:
                deltaString = f"(+{delta})" if delta > 0 else f"({delta})"
            else:
                deltaString = ""
            valueString += f"{rank}. **{player}**: **{rating}** {deltaString}\n"

        embed.add_field(name=region, value=valueString, inline=True)

    return embed


if __name__ == "__main__":
    leaderboardBot = LeaderBoardBot()
    buddyDict = get_buddy_dict()
    bot.run(os.environ["DISCORD_TOKEN"])
