# import asyncio
from dis import disco
import os
from datetime import datetime

# import aiocron
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pytz import timezone, utc
import default_alias
from leaderboard_queries import LeaderboardDB

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

channelIds = {
    "wall_lii": 811468284394209300,
    "wall-lii-requests": 846867129834930207,
    "test": 730782280674443327,
}

liiDiscordId = 729524538559430670
compHSDiscordId = 939711967134887998
compHSDiscordChannelId = 1242140313242566708
frontpage_channel_id = 1096490528947851304
frontpage_message_id = 1096514937813217370

emotes = ["liiHappyCat", "liiCat", "ninaisFEESH", "liiWait"]


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")

async def process_bgrank(
    responder,  # Function to handle the response (e.g., ctx.respond or channel.send)
    player_name,
    region=None,
    game_mode="0"
):
    try:
        # If a region is specified
        if region:
            response = db.format_player_stats(player_name, region, game_mode)
            await responder(response)
        else:
            # Handle case where no region is provided
            if player_name.isdigit():
                servers = ["NA", "EU", "AP"]
                responses = []
                for srv in servers:
                    response = db.format_player_stats(player_name, srv, game_mode)
                    if "No player found" not in response:
                        responses.append(response)
                if responses:
                    await responder(" | ".join(responses))
                else:
                    await responder("No player found across all regions.")
            else:
                response = db.format_player_stats(player_name, "", game_mode)
                if "No player found" not in response:
                    await responder(response)
                else:
                    await responder("Invalid input. Please provide a valid player name or rank.")
    except Exception as e:
        await responder("An error occurred while processing the command.")
        print(f"Error in process_bgrank: {e}")

async def process_bgdaily(
    responder,  # Function to handle the response (e.g., ctx.respond or channel.send)
    player_name,
    region=None,
    game_mode="0"
):
    try:
        # If a region is specified
        if player_name.isdigit() and region is None:
            await responder("Server needs to be specified with rank lookups.")
        else:
            response = db.format_daily_stats(player_name, region, game_mode)
            await responder(response)
    except Exception as e:
        await responder("An error occurred while processing the command.")
        print(f"Error in process_bgdaily: {e}")

async def process_bgweekly(
    responder,  # Function to handle the response (e.g., ctx.respond or channel.send)
    player_name,
    region=None,
    game_mode="0"
):
    try:
        # If a region is specified
        if player_name.isdigit() and region is None:
            await responder("Server needs to be specified with rank lookups.")
        else:
            response = db.format_weekly_stats(player_name, region, game_mode)
            await responder(response)
    except Exception as e:
        await responder("An error occurred while processing the command.")
        print(f"Error in process_bgweekly: {e}")

async def process_peak(
    responder,  # Function to handle the response (e.g., ctx.respond or channel.send)
    player_name,
    region=None,
    game_mode="0"
):
    try:
        # If a region is specified
        if player_name.isdigit() and region is None:
            await responder("Server needs to be specified with rank lookups.")
        else:
            response = db.format_peak_stats(player_name, region, game_mode)
            await responder(response)
    except Exception as e:
        await responder("An error occurred while processing the command.")
        print(f"Error in process_peak: {e}")

async def process_stats(
    responder,  # Function to handle the response (e.g., ctx.respond or channel.send)
    server=None,
    game_mode="0"
):
    try:
        if server is None or server == "":
            servers = ["NA", "EU", "AP"]
            responses = []
            for srv in servers:
                response = db.format_region_stats(srv, game_mode)
                if "No stats available" not in response:
                    # Omit the maximum MMR part
                    response = response.split(". The highest rating is")[0]
                    responses.append(response)
            await responder(" | ".join(responses))
        else:
            response = db.format_region_stats(server, game_mode)
            await responder(response)
    except Exception as e:
        await responder("An error occurred while processing the command.")
        print(f"Error in process_stats: {e}")

async def process_top(
    responder,  # Function to handle the response (e.g., ctx.respond or channel.send)
    server=None,
    game_mode="0"
):
    try:
        if server is None or server == "":
            players = db.get_top_players_global(game_mode)
            if not players:
                await responder("No players found globally")
                return

            # Format each player as "name (rating) from server"
            formatted = [
                f"{i+1}. {p['PlayerName']}: {p['LatestRating']} ({p['Server']})"
                for i, p in enumerate(players)
            ]

            await responder(f"Top 10 globally: {', '.join(formatted)}")
        else:
            response = db.format_top_players(server, game_mode)
            await responder(response)
    except Exception as e:
        await responder("An error occurred while processing the command.")
        print(f"Error in process_top: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("!bgrank") or message.content.startswith("!rank") or message.content.startswith("!duorank"):
        args = message.content.split()
        if len(args) > 1:
            player_name = args[1]
            region = args[2] if len(args) > 2 else None
            game_mode = "1" if message.content.startswith("!duorank") else "0"
            await process_bgrank(message.channel.send, player_name, region, game_mode)
        else:
            await message.channel.send("Usage: !bgrank <player_name or rank> [region]")

    if message.content.startswith("!bgdaily") or message.content.startswith("!daily") or message.content.startswith("!day") or message.content.startswith("!duodaily") or message.content.startswith("!duoday"):
        args = message.content.split()
        if len(args) > 1:
            player_name = args[1]
            region = args[2] if len(args) > 2 else None
            game_mode = "1" if message.content.startswith("!duodaily" or message.content.startswith("!duoday")) else "0"
            await process_bgdaily(message.channel.send, player_name, region, game_mode)
        else:
            await message.channel.send("Usage: !daily <player_name or rank> [region]")

    if message.content.startswith("!bgweekly") or message.content.startswith("!weekly") or message.content.startswith("!week") or message.content.startswith("!duoweek") or message.content.startswith("!duoweekly"):
        args = message.content.split()
        if len(args) > 1:
            player_name = args[1]
            region = args[2] if len(args) > 2 else None
            game_mode = "1" if message.content.startswith("!duoweekly" or message.content.startswith("!duoweek")) else "0"
            await process_bgweekly(message.channel.send, player_name, region, game_mode)
        else:
            await message.channel.send("Usage: !weekly <player_name or rank> [region]")

    if message.content.startswith("!peak") or message.content.startswith("!duopeak"):
        args = message.content.split()
        if len(args) > 1:
            player_name = args[1]
            region = args[2] if len(args) > 2 else None
            game_mode = "1" if message.content.startswith("!duopeak") else "0"
            await process_peak(message.channel.send, player_name, region, game_mode)
        else:
            await message.channel.send("Usage: !peak <player_name or rank> [region]")

    if message.content.startswith("!stats") or message.content.startswith("!bgstats") or message.content.startswith("!duostats"):
        args = message.content.split()
        region = args[1] if len(args) > 1 else None
        game_mode = "1" if message.content.startswith("!duostats") else "0"
        await process_stats(message.channel.send, region, game_mode)

    if message.content.startswith("!top") or message.content.startswith("!bgtop") or message.content.startswith("!duotop"):
        args = message.content.split()
        region = args[1] if len(args) > 1 else None
        game_mode = "1" if message.content.startswith("!duotop") else "0"
        await process_top(message.channel.send, region, game_mode)

    if message.content.startswith("!patch"):
        await message.channel.send(db.get_patch_link())

    if message.content.startswith("!help"):
        await message.channel.send("Available commands: !bgrank, !bgdaily, !bgweekly, !peak, !stats, !top, !duorank, !duodaily, !duoweekly, !duopeak, !duostats, !duotop")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's rank"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def bgrank(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_bgrank(ctx.respond, player_name, region, game_mode="0")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's duo rank"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def duorank(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_bgrank(ctx.respond, player_name, region, game_mode="1")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's daily stats"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def daily(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_bgdaily(ctx.respond, player_name, region, game_mode="0")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's duo daily stats"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def duodaily(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_bgdaily(ctx.respond, player_name, region, game_mode="1")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's weekly stats"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def weekly(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_bgweekly(ctx.respond, player_name, region, game_mode="0")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's duo weekly stats"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def duoweekly(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_bgweekly(ctx.respond, player_name, region, game_mode="1")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's peak stats"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def peak(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_peak(ctx.respond, player_name, region, game_mode="0")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a player's duo peak stats"
)
@discord.option("player_name", description="Enter the player's name or rank")
@discord.option("region", description="Enter the player's region", default=None)
async def duopeak(ctx: discord.ApplicationContext, player_name: str, region: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_peak(ctx.respond, player_name, region, game_mode="1")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get a region's stats"
)
@discord.option("server", description="Enter the server", default=None)
async def stats(ctx: discord.ApplicationContext, server: str):
    await ctx.defer()  # Optional, if processing might take longer than 3 seconds
    await process_stats(ctx.respond, server, game_mode="0")

@bot.slash_command(
    guild_ids=[liiDiscordId],
    description="Add alias"
)
@discord.option("alias", description="The alias for the player name")
async def addalias(ctx: discord.ApplicationContext, alias: str, player_name: str):
    await ctx.respond(db.add_alias(alias, player_name))

@bot.slash_command(
    guild_ids=[liiDiscordId],
    description="Delete alias"
)
@discord.option("alias", description="The alias for the player name")
async def deletealias(ctx: discord.ApplicationContext, alias: str):
    await ctx.respond(db.delete_alias(alias))

@bot.slash_command(
    guild_ids=[liiDiscordId],
    description="Add channel"
)
@discord.option("channel", description="The channel name")
@discord.option("player_name", description="The channel's player name", default=None)
async def addchannel(ctx: discord.ApplicationContext, channel: str, player_name: str):
    await ctx.respond(db.add_channel(channel, player_name))

@bot.slash_command(
    guild_ids=[liiDiscordId],
    description="Delete channel"
)
@discord.option("channel", description="The channel name")
async def deletechannel(ctx: discord.ApplicationContext, channel: str):
    await ctx.respond(db.delete_channel(channel))

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get wall_lii commands"
)
async def help(ctx: discord.ApplicationContext):
    await ctx.respond(
        "Available commands with ! or /:\n"
        "!bgrank <player_name or rank> [region]\n"
        "!daily <player_name or rank> [region]\n"
        "!weekly <player_name or rank> [region]\n"
        "!peak <player_name or rank> [region]\n"
        "!stats [region]\n"
        "!top [region]\n")

@bot.slash_command(
    guild_ids=[liiDiscordId, compHSDiscordId],
    description="Get the latest battlegrounds patch notes link"
)
async def patch(ctx: discord.ApplicationContext):
    patch_link = db.get_patch_link()
    await ctx.respond(patch_link)

if __name__ == "__main__":
  db = LeaderboardDB(table_name="HearthstoneLeaderboardV2")
  bot.run(os.environ["DISCORD_TOKEN"])