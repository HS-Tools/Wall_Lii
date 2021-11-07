# HS-BG-Leaderboards-Bot
Fetches Hearthstone Battlegrounds Leaderboard information every 3 minutes to enable users to get the current rank of a player and to fetch their daily record of games.

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