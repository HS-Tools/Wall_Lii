# Hearthstone Battlegrounds Leaderboard Bot

## Overview

A Twitch chat bot that tracks real-time Hearthstone Battlegrounds leaderboard statistics, including player rankings, MMR changes, and daily/weekly progress.

## Core Components

### 1. Data Collection (AWS Lambda)

- Fetches leaderboard data every 2 minutes
- Supports both game modes:
  - Regular Battlegrounds (mode: 0)
  - Battlegrounds Duo (mode: 1)
- Covers all servers (NA, EU, AP)
- Uses UTC timestamps for consistency
- Optimized logging (only significant changes >301 MMR)
- Handles duplicate player names:
  - Tracks name occurrences per server/mode
  - Appends count to duplicate names (e.g., "mia2")
  - Logs duplicate name occurrences
  - Ensures unique player keys in database

### 2. Data Storage (DynamoDB)

- Schema:
  - Primary Key: GameModeServerPlayer (e.g., "0#NA#beterbabbit")
  - GSI: RankLookupIndex (GameModeServer, CurrentRank)
  - RatingHistory: Array of [rating, timestamp] pairs
- Environments:
  - Development: HearthstoneLeaderboard (local)
  - Production: HearthstoneLeaderboardV2 (AWS)

### 3. Bot Interface

- Supports both local and AWS DynamoDB via --aws flag
- Handles player lookups and rank queries
- Supports multiple game modes and servers
- Provides formatted responses for chat
- Supports player aliases and default channel names

### 4. Player Resolution

- Aliases:

  - Maps alternative names to actual player names
  - Example: "beter" → "beterbabbit", "hapa" → "hapabear"
  - Stored in alias table for easy updates
  - All player lookup commands support aliases:
    - !bgrank
    - !bgdaily
    - !bgweekly
    - !peak
  - Alias Management:
    - Check alias table for updates every minute
    - Support for new aliases, updates, and deletions
    - Maintain local cache for performance
    - No service interruption during updates

- Default Channel Names:
  - Each Twitch channel can have a default player name
  - Used when commands are called with no arguments
  - Example: "!bgrank" in channel "liihs" resolves to "!bgrank lii"

## Commands and Responses

### Player Stats

1. `!bgrank <player|rank> [server]`

   ```
   # Default channel lookup (no arguments)
   {default_player} is rank {rank} in {server} at {rating}

   # Alias lookup
   {resolved_player} is rank {rank} in {server} at {rating}

   # Player lookup
   {player} is rank {rank} in {server} at {rating}

   # Player lookup (multiple servers)
   {player} is rank {rank} in {server} at {rating} (also rank {rank2} {server2} at {rating2})

   # Rank lookup
   {player} is rank {rank} in {server} at {rating}
   ```

2. `!bgdaily <player|rank> [server]`

   ```
   # Default channel and alias lookups supported
   # With games played
   {player} started today at {start_rating} in {server} and is now {current_rating} with {games} games played. Their record is: {changes}

   # No games played
   {player} is rank {rank} in {server} at {rating} with 0 games played
   ```

3. `!bgweekly <player|rank> [server]`

   ```
   # Default channel and alias lookups supported
   # With games played
   {player} started the week at {start_rating} in {server} and is now {current_rating} with {games} games played. [{daily_changes}]

   # No games played
   {player} is rank {rank} in {server} at {rating} with 0 games played this week
   ```

4. `!peak <player|rank> [server]`
   ```
   # Default channel and alias lookups supported
   {player}'s peak rating in {server}: {rating}
   ```

### Server Stats

1. `!stats <server>`

   ```
   {server} has {count} players with an average rating of {avg_rating}. The highest rating is {max_rating}
   ```

2. `!top <server>`
   ```
   Top 5 {server}: 1. {player1} ({rating1}), 2. {player2} ({rating2})...
   ```

### Error Responses

```
# Invalid server
Invalid server: {server}. Valid servers are: NA, EU, AP

# Player not found
{player} is not on any BG leaderboards

# Rank lookup errors
Server is required for rank lookup
No player found at rank {rank} in {server}
```

## Data Rules

1. Rating Updates

   - Store new rating if changed and 60+ seconds since last update
   - Prevent duplicate entries within last 3 updates
   - Track significant changes (>301 MMR)

2. Time Handling

   - All timestamps in UTC
   - Daily stats: last 24 hours
   - Weekly stats: last 7 days
   - Peak rating: all-time

3. Server Validation

   - Valid servers: NA, EU, AP
   - US automatically maps to NA
   - Case-insensitive handling

4. Name Resolution
   - Alias resolution takes precedence over direct lookups
   - Default channel name used when no arguments provided
   - Commands supporting default names:
     - !bgrank
     - !bgdaily
     - !bgweekly
     - !peak

### Player Stats

Each command has a duo mode version that queries Battlegrounds Duo leaderboard:

- !bgrank → !duorank
- !bgdaily → !duodaily
- !bgweekly → !duoweekly
- !peak → !duopeak

1. `!bgrank <player|rank> [server]`

   ```
   # Default channel lookup (no arguments)
   {default_player} is rank {rank} in {server} at {rating}

   # Player lookup
   {player} is rank {rank} in {server} at {rating}

   # Player lookup (multiple servers)
   {player} is rank {rank} in {server} at {rating} (also rank {rank2} {server2} at {rating2})
   ```

### Server Stats

Each command has a duo mode version that shows Battlegrounds Duo stats:

- !stats → !duostats
- !top → !duotop

1. `!stats <server>`
   ```
   {server} has {count} players with an average rating of {avg_rating}. The highest rating is {max_rating}
   ```

## Data Rules

1. Rating Updates

   - Store new rating if changed and 60+ seconds since last update
   - Prevent duplicate entries within last 3 updates
   - Track significant changes (>301 MMR)

2. Time Handling

   - All timestamps in UTC
   - Daily stats: last 24 hours
   - Weekly stats: last 7 days
   - Peak rating: all-time

3. Server Validation

   - Valid servers: NA, EU, AP
   - US automatically maps to NA
   - Case-insensitive handling

4. Name Resolution
   - Alias resolution takes precedence over direct lookups
   - Default channel name used when no arguments provided
   - Commands supporting default names:
     - !bgrank
     - !bgdaily
     - !bgweekly
     - !peak

### Player Stats

Each command has a duo mode version that queries Battlegrounds Duo leaderboard:

- !bgrank → !duorank
- !bgdaily → !duodaily
- !bgweekly → !duoweekly
- !peak → !duopeak

1. `!bgrank <player|rank> [server]`

   ```
   # Default channel lookup (no arguments)
   {default_player} is rank {rank} in {server} at {rating}

   # Player lookup
   {player} is rank {rank} in {server} at {rating}

   # Player lookup (multiple servers)
   {player} is rank {rank} in {server} at {rating} (also rank {rank2} {server2} at {rating2})
   ```

### Server Stats

Each command has a duo mode version that shows Battlegrounds Duo stats:

- !stats → !duostats
- !top → !duotop

1. `!stats <server>`
   ```
   {server} has {count} players with an average rating of {avg_rating}. The highest rating is {max_rating}
   ```

## Data Rules

1. Rating Updates

   - Store new rating if changed and 60+ seconds since last update
   - Prevent duplicate entries within last 3 updates
   - Track significant changes (>301 MMR)

2. Time Handling

   - All timestamps in UTC
   - Daily stats: last 24 hours
   - Weekly stats: last 7 days
   - Peak rating: all-time

3. Server Validation

   - Valid servers: NA, EU, AP
   - US automatically maps to NA
   - Case-insensitive handling

4. Name Resolution
   - Alias resolution takes precedence over direct lookups
   - Default channel name used when no arguments provided
   - Commands supporting default names:
     - !bgrank
     - !bgdaily
     - !bgweekly
     - !peak

### Player Stats

Each command has a duo mode version that queries Battlegrounds Duo leaderboard:

- !bgrank → !duorank
- !bgdaily → !duodaily
- !bgweekly → !duoweekly
- !peak → !duopeak

1. `!bgrank <player|rank> [server]`

   ```
   # Default channel lookup (no arguments)
   {default_player} is rank {rank} in {server} at {rating}

   # Player lookup
   {player} is rank {rank} in {server} at {rating}

   # Player lookup (multiple servers)
   {player} is rank {rank} in {server} at {rating} (also rank {rank2} {server2} at {rating2})
   ```

### Server Stats

Each command has a duo mode version that shows Battlegrounds Duo stats:

- !stats → !duostats
- !top → !duotop

1. `!stats <server>`
   ```
   {server} has {count} players with an average rating of {avg_rating}. The highest rating is {max_rating}
   ```

## Data Rules

1. Rating Updates

   - Store new rating if changed and 60+ seconds since last update
   - Prevent duplicate entries within last 3 updates
   - Track significant changes (>301 MMR)

2. Time Handling

   - All timestamps in UTC
   - Daily stats: last 24 hours
   - Weekly stats: last 7 days
   - Peak rating: all-time

3. Server Validation

   - Valid servers: NA, EU, AP
   - US automatically maps to NA
   - Case-insensitive handling

4. Name Resolution
   - Alias resolution takes precedence over direct lookups
   - Default channel name used when no arguments provided
   - Commands supporting default names:
     - !bgrank
     - !bgdaily
     - !bgweekly
     - !peak

### Player Stats

Each command has a duo mode version that queries Battlegrounds Duo leaderboard:

- !bgrank → !duorank
- !bgdaily → !duodaily
- !bgweekly → !duoweekly
- !peak → !duopeak

1. `!bgrank <player|rank> [server]`

   ```
   # Default channel lookup (no arguments)
   {default_player} is rank {rank} in {server} at {rating}

   # Player lookup
   {player} is rank {rank} in {server} at {rating}

   # Player lookup (multiple servers)
   {player} is rank {rank} in {server} at {rating} (also rank {rank2} {server2} at {rating2})
   ```

### Server Stats

Each command has a duo mode version that shows Battlegrounds Duo stats:

- !stats → !duostats
- !top → !duotop

1. `!stats <server>`
   ```
   {server} has {count} players with an average rating of {avg_rating}. The highest rating is {max_rating}
   ```

## Data Rules

1. Rating Updates

   - Store new rating if changed and 60+ seconds since last update
   - Prevent duplicate entries within last 3 updates
   - Track significant changes (>301 MMR)

2. Time Handling

   - All timestamps in UTC
   - Daily stats: last 24 hours
   - Weekly stats: last 7 days
   - Peak rating: all-time

3. Server Validation

   - Valid servers: NA, EU, AP
   - US automatically maps to NA
   - Case-insensitive handling

4. Name Resolution
   - Alias resolution takes precedence over direct lookups
   - Default channel name used when no arguments provided
   - Commands supporting default names:
     - !bgrank
     - !bgdaily
     - !bgweekly
     - !peak
