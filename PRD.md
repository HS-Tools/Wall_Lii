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
