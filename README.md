# Wall_lii

Wall_lii is a Twitch and Discord bot that stores leaderboard and game data for Hearthstone Battlegrounds. It provides helpful commands for users to:

- Check a player's rank.
- Get a player's daily and weekly progress.
- View the top players in each server.
- Access relevant information about game mechanics.

## Setup as a Streamer

Great news! No need to manually set up the bot yourself. Wall_lii is running and freely available to all Twitch streamers. To get started:

1. Join liihs's [Discord](https://discord.com/invite/C6NguFf).
2. Navigate to the `#wall-lii-requests` channel.
3. Follow the directions in the pinned message to request Wall_lii to join your channel.

Wall_lii automatically joins channels on its list when they go live.

### Troubleshooting

If the bot does not respond to your commands, it is likely due to followers-only chat being enabled. To ensure the bot can respond:

- Add the bot as a VIP or Moderator, similar to other bots.

## Commands

### Player Stats Commands

- **`!rank <game name>`**: Displays the player's rank and MMR in their highest-rated region.  
  - Duo version: **`!duorank <game name>`**

- **`!day <game name>`**: Shows the player's starting MMR, current MMR, and a list of MMR changes from games played during the day. Resets daily at midnight PST.  
  - Duo version: **`!duoday <game name>`**

- **`!yday <game name>`**: Works like `!day` but for yesterday.  
  - Duo version: **`!duoyday <game name>`**

- **`!week <game name>`**: Provides weekly stats, including starting and current MMR, daily changes, and total games played during the week.  
  - Duo version: **`!duoweek <game name>`**

- **`!lweek <game name>`**: Works like `!week` but for last week.  
  - Duo version: **`!duolweek <game name>`**

- **`!peak <game name>`**: Shows the player's peak rating and associated server.  
  - Duo version: **`!duopeak <game name>`**

### Buddy Commands

- **`!buddy <game name>`**: Displays the player's current buddy and its stats.  

- **`!goldenbuddy <game name>`**: Shows information about the player's golden buddy, including stats and progress to completion.  

- **`!trinket <game name>`**: Provides details about the player's equipped trinkets and their effects.  

### Milestone Commands

- **`!8k <server>`**: Shows the first player to reach the 8000 MMR milestone on a specified server.  
  - Example: **`!8k na`** for the NA server.  

- **`!8k`**: Displays the first player to reach the 8000 MMR milestone globally, across all servers.

Milestone commands are available for all milestones in 1000-MMR increments, such as **`!9k`**, **`!10k`**, etc.

### Server Stats Commands

- **`!stats <server>`**: Displays server statistics, including the number of players, average rating, and the highest rating.  
  - Examples:  
    - **`!stats na`**: Stats for the NA server.  
    - **`!stats`**: Stats for all servers (NA, EU, AP).  
  - Duo version: **`!duostats <server>`**

- **`!top <server>`**: Lists the top 10 players for a specified server.  
  - Examples:  
    - **`!top na`**: Top 10 players in NA.  
    - **`!top`**: Global top 10 players.  
  - Duo version: **`!duotop <server>`**

### Fun Commands

- **`!goodbot`**: Praises the bot with a fun response.
- **`!wall_lii`**: Displays help and information about the bot’s features.

## Contributing

We welcome contributions from the community! Please maintain civility in Issues, Pull Requests, and all communication regarding this project.

### Getting Started

Contributors can start by reviewing the bot’s functionality and suggesting or implementing enhancements. We recommend creating issues for discussions before submitting pull requests.

## How to Run

Documentation for setting up and running the bot is in progress. Check back soon for updates.

## Testing

Testing instructions and processes are currently being developed. Updates will be provided as they become available.
