# HS-BG-Leaderboards-Bot
Fetches Hearthstone Battlegrounds Leaderboard information regularly to enable users to get the current rank of a player and to fetch their daily record of games. 

# Setup as a streamer
Great news! No need to manually setup the bot to run for you. We have the bot running and freely available to all twitch stremers. Just go to liihs's [discord](https://discord.com/invite/C6NguFf). From there go to the channel `#wall-lii-requests` and use the directions in the pinned message.

Once the bot is connected to you chat you will see it under the viewers list.

You can test the commands, and if the bot doesn't respond to you, probably you have followers only chat enabled. To make sure that the bot can respond, you can make him a VIP or Moderator, like any other bot.

# Commands:
* !bgrank {battletag}: Gets the rank and mmr of a player in their highest rated region
* !bgdaily {battletag}: Gets the starting mmr, current mmr and the list of mmr changes from all games played during the day. This resets at midnight PST time
* !wall_lii: Help command
* !goodbot: Praise the bot

# How to run:
`rpi.sh`

# Testing
This branch uses a local download of the dynamodb-local and an in memory database to make tests run much more quickly
## Requirements
- java
    - `brew install java` on a mac
- unzip
- curl

## Setup
1. download using `./scripts/download-dynamodb-local.sh`
2. run using `./scripts/run-dynamodb-local.sh dynamodb-local`
3. open a 2nd terminal

## Run Tests
`pipenv run python testFile.py`

## Troubleshooting
- If the old docker-compose test environment is still running then the java script program will not run. Stop the old docker-compose programs before starting the java based test environment.
