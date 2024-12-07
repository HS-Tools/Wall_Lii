# HS-BG-Leaderboards-Bot

Fetches Hearthstone Battlegrounds Leaderboard information regularly to enable users to get the current rank of a player and to fetch their daily record of games.

# Setup as a streamer

Currently, the bot is not available to add until I make some updates to the code.

~~Great news! No need to manually setup the bot to run for you. We have the bot running and freely available to all twitch stremers. Just go to liihs's [discord](https://discord.com/invite/C6NguFf). From there go to the channel `#wall-lii-requests` and use the directions in the pinned message.~~

Once the bot is connected to you chat you will see it under the viewers list.

You can test the commands, and if the bot doesn't respond to you, probably you have followers only chat enabled. To make sure that the bot can respond, you can make him a VIP or Moderator, like any other bot.

# Commands:

- !bgrank {battletag}: Gets the rank and mmr of a player in their highest rated region
- !bgdaily {battletag}: Gets the starting mmr, current mmr and the list of mmr changes from all games played during the day. This resets at midnight PST time
- !wall_lii: Help command
- !goodbot: Praise the bot

# Contributing

We welcome all contributors. Please be civil in Issues, Pull Requests, and all work regarding this project.

Be sure to install pre-commit:

Pre-Commit: https://pre-commit.com/

```
pre-commit install
```

# How to run:

`start.sh`

# Testing

We have unit tests. Instructions for running them locally can be found [here](./test). Tests are also run in CI.

## Troubleshooting

- If the old docker-compose test environment is still running then the java script program will not run. Stop the old docker-compose programs before starting the java based test environment.
