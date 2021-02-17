import threading
import os
import discord
from currentDay import getCurrentDay

discordBot = discord.Client()

@discordBot.event
async def on_ready():
    print('{} connected to discord'.format(discordBot.user))

@discordBot.event
async def on_message(message):
    if message.author == discordBot.user:
        return

    if message.content == '99!':
        await message.channel.send('hi')


discordThread = threading.Thread(target=discordBot.run, args=[os.environ['DISCORD_TOKEN']])
discordThread.setDaemon(True)
discordThread.start()


# discordBot.run(os.environ['DISCORD_TOKEN'])

# # Run a thread for the discord bot
# discordBotThread = threading.Thread(target=discordBot.run, args=(os.environ['DISCORD_TOKEN']))
# # discordBotThread.daemon = True
# discordBotThread.start()
