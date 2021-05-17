# HS-BG-Leaderboards-Bot
Fetches Hearthstone Battlegrounds Leaderboard information every 3 minutes to enable users to get the current rank of a player and to fetch their daily record of games.

# Commands:
* !bgrank {battletag}: Gets the rank and mmr of a player in their highest rated region
* !bgdaily {battletag}: Gets the starting mmr, current mmr and the list of mmr changes from all games played during the day. This resets at midnight PST time
* !wall_lii: Help command
* !goodbot: Praise the bot

# How to run:
`rpi.sh`

# How to test in full container:
1. build with `docker-compose build`
2. run with `docker-compose run app-node`

# How to test in partial container:
1. run `docker-compose up`
2. in a seperate terminal `pipenv run python testLeaderboard.py` or other test file