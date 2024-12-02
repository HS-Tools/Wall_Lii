# Hearthstone Battlegrounds Leaderboard Bot - Product Requirements Document

## Product Overview

A Twitch chat bot that tracks and provides real-time Hearthstone Battlegrounds leaderboard statistics, including player rankings, MMR changes, and daily/weekly progress.

## Core Components

### 1. Twitch Bot

- Responds to chat commands for player stats and rankings
- Handles player aliases for easier lookups
- Supports multiple game modes (Battlegrounds, Battlegrounds Duo)
- Supports multiple regions (NA, EU, AP)
- Provides real-time MMR and rank information

### 2. AWS Lambda Function

- Periodically fetches leaderboard data from Blizzard's API
- Stores player data in DynamoDB
- Tracks MMR changes and rank updates
- Currently debugging data freshness issues with specific players (e.g., beterbabbit)

### 3. Data Storage

- Uses AWS DynamoDB for persistent storage
- Maintains player history for statistical analysis
- Stores player aliases and channel configurations

## Key Features

### Current Features

1. **Player Lookups**

   - `!bgrank <player> <region>` - Current rank and MMR
   - `!bgdaily <player> <region>` - Daily MMR changes and games played
   - `!bgweekly <player> <region>` - Weekly progress and MMR trends
   - `!duorank <player> <region>` - Current duo rank and MMR
   - `!duodaily <player> <region>` - Daily duo MMR changes and games played
   - `!duoweekly <player> <region>` - Weekly duo progress and MMR trends

2. **Rank Lookups**

   - Look up players by rank (e.g., `!bgrank 1 na`)
   - Support for top 1000 players

3. **Alias System**
   - Custom aliases for popular players
   - Automatic alias resolution

### Data Management

- Stores historical MMR data
- Tracks player performance over time
- Updates data periodically via Lambda function

## Technical Requirements

### Infrastructure

- AWS Lambda for data collection
- DynamoDB for data storage
- Python-based bot implementation
- AWS SAM for Lambda deployment

### Dependencies

- boto3 for AWS interactions
- python-dotenv for configuration
- requests for API calls
- aiocron for scheduled tasks

## Current Issues/Improvements Needed

1. Lambda function data freshness

   - Investigating update frequency
   - Adding debug logging for specific players
   - Verifying data storage logic

2. Local Development
   - Improving development environment setup
   - Streamlining deployment process
   - Better handling of local vs. production configurations

3. Scaling Requirements
   - Currently fetching top 100 players per region
   - Short term: Scale to 1000 players per region
   - Long term: Scale to 10000 players per region
   - Need to optimize Lambda performance and timeout settings
   - Consider parallel processing and batch updates

### Data Access Patterns

#### Primary Access Patterns
1. **Player Lookup (Most Common)**
   - Input: PlayerName (partial/full), GameMode
   - Output: Current rank and latest rating
   - Query Requirements:
     - Fast player name search (case-insensitive)
     - Filter by game mode
     - Access latest rating without scanning full history
     - Compare ranks across servers for same player

2. **Rank Lookup (Common)**
   - Input: Rank, GameMode, Server
   - Output: Player's latest rating
   - Query Requirements:
     - Direct access by rank within a server/mode combination
     - Access latest rating without scanning full history

### Proposed Table Structure

#### Main Table Design
- **Partition Key**: `{GameMode}#{Server}#{PlayerName}`
  - Example: "0#NA#kripp" (for Battlegrounds NA player)
- **Sort Key**: `Season`
  - Enables historical season data queries

#### Attributes
- **CurrentRank**: Number
- **LatestRating**: Number (denormalized for quick access)
- **RatingHistory**: List[Tuple]
  - Format: [[rating, epoch], ...]
  - Latest rating always at end of list

#### Global Secondary Indexes (GSIs)

1. **RankLookupIndex**
   - Partition Key: `{GameMode}#{Server}#{Season}`
   - Sort Key: `CurrentRank`
   - Projected Attributes:
     - PlayerName
     - LatestRating
   - Optimizes rank-based queries

2. **PlayerLookupIndex**
   - Partition Key: `PlayerName`
   - Sort Key: `{GameMode}#{Season}`
   - Projected Attributes:
     - CurrentRank
     - LatestRating
     - Server
   - Enables cross-server player searches

### Query Implementations

1. **Player Search Query**

### Lambda Function Specification

#### Basic Configuration
- Execution Frequency: 2 minutes (configurable)
- Timeout: TBD based on performance testing
- Memory: TBD based on performance testing

#### Data Collection Process
1. **API Endpoints**
   - Format: `https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData`
   - Parameters:
     - region: US, EU, AP
     - leaderboardId: battlegrounds, battlegroundsduo
     - seasonId: current season
     - page: 1-N (25 players per page)

2. **Pagination Handling**
   - Fetch 25 players per API call
   - Continue until either:
     - No more players available
     - Reached configured player limit (X)
   - Handle empty/invalid responses gracefully

3. **Data Processing Rules**
   - **New Players**
     ```
     If no entry exists for (PlayerName, Region, GameMode):
         Create new entry with current rank/rating
     ```
   
   - **Existing Players**
     ```
     If entry exists:
         Update current rank
         If current rating != latest rating in history:
             Append new rating to history
     ```

   - **Name Collision Handling**
     ```
     If duplicate name detected (same name, different rank/rating):
         If cannot verify identity:
             Create new entry with incrementing suffix
             Flag entry for potential manual review
         Track collision in separate table for monitoring
     ```

#### Error Handling
1. **API Failures**
   - Implement exponential backoff
   - Log failed requests
   - Continue with remaining regions/modes

2. **Data Validation**
   - Verify rating ranges are reasonable
   - Validate player name formats
   - Check for impossible rank changes

#### Monitoring
1. **Performance Metrics**
   - API response times
   - Processing time per batch
   - Number of players processed

2. **Data Quality Metrics**
   - Number of name collisions
   - Invalid data points
   - Missing data points

#### Future Considerations
1. **Rate Limiting**
   - Monitor API usage limits
   - Implement request throttling if needed

2. **Data Cleanup**
   - Archive historical data
   - Clean up unresolved name collisions