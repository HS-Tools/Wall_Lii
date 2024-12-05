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
  - GSI: PlayerLookupIndex (PlayerName, GameMode)
  - RatingHistory: Array of [rating, timestamp] pairs
- MilestoneTracking
  - Primary Key: SeasonGameModeServer (e.g., "14-0-NA")
  - Sort Key: Milestone (e.g., 8000)
  - Attributes: PlayerName, Rating, Timestamp
- player-alias-table
  - Stores player name aliases
  - Used for resolving alternative names
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
2. `!bgdaily/!duodaily <player|rank> [server]`
   # Default channel and alias lookups supported
   # With games played
   {player} climbed/fell from {start_rating} to {current_rating} ({change}) in {server} over {games} games: [{changes}] liiHappyCat/liiCat
   # No games played
   {player} is rank {rank} in {server} at {rating} with 0 games played
3. `!bgweekly/!duoweekly <player|rank> [server]`
   {player} climbed/fell from {start_rating} to {current_rating} ({change}) in {server} over {games} games: [{daily_changes}] liiHappyCat/liiCat
   {player} is rank {rank} in {server} at {rating} with 0 games played this week
4. `!peak <player|rank> [server]`
   {player}'s peak rating in {server}: {rating}
### Milestone Stats
1. Rating Milestones (!8k through !18k)
   - Track first player to reach each 1000-rating milestone (8000, 9000, etc.)
   - Support server-specific queries (!8k na) and global queries (!8k)
   - Show player name, server, and date of achievement
   - Data Storage:
     - Separate DynamoDB table for milestone tracking
       Primary Key: SeasonId-GameMode-Server-Milestone (e.g., "1-0-NA-8000")
       Attributes:
         - PlayerName: First player to reach milestone
         - Timestamp: When milestone was reached (UTC)
         - Rating: Exact rating when milestone was reached
   - Lambda Processing:
     - Efficient Milestone Checking:
       - Query highest milestone achieved for current season/server/game mode
       - Only check top player's rating against next milestone
       - Example: If highest milestone is 13000, only check top player for 14000
     - Write new milestone record when:
       - Top player's rating exceeds next milestone threshold
       - No existing record for that milestone in current season
     - Timestamps stored in UTC for consistency
     - Track milestones per season/server/game mode
     - Efficient querying without scanning main leaderboard table
   - Example responses:
     # Server specific
     {player} was the first to reach {k}k in {server} on {date}
     # Global (any server)
     {player} was the first to reach {k}k (in {server}) on {date}
     # Not reached
     No one has reached {k}k in {server} yet!
     No one has reached {k}k in any server yet!
### Server Stats
1. `!stats <server>`
   {server} has {count} players with an average rating of {avg_rating}. The highest rating is {max_rating}
2. `!top <server>`
   Top 5 {server}: 1. {player1} ({rating1}), 2. {player2} ({rating2})...
### Error Responses
# Invalid server
Invalid server: {server}. Valid servers are: NA, EU, AP
# Player not found
{player} is not on any BG leaderboards
# Rank lookup errors
Server is required for rank lookup
No player found at rank {rank} in {server}
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
Each command has a duo mode version that queries Battlegrounds Duo leaderboard:
- !bgrank → !duorank
- !bgdaily → !duodaily
- !bgweekly → !duoweekly
- !peak → !duopeak
Each command has a duo mode version that shows Battlegrounds Duo stats:
- !stats → !duostats
- !top → !duotop
   # No server specified (shows all servers)
   NA has {count} players with average {avg} | EU has {count} players with average {avg} | AP has {count} players with average {avg}
2. `!bgtop <server>` and `!duotop <server>`
   # Single server
   Top 10 {server}: 1. {player1}: {rating1}, 2. {player2}: {rating2}...
   # No server specified (shows global top 10)
   Top 10 globally: 1. {player1}: {rating1} ({server1}), 2. {player2}: {rating2} ({server2})...
### Command Naming Convention
All regular Battlegrounds commands now have a "bg" prefix to distinguish them from duo mode:
Duo mode commands use "duo" prefix:
### Help Command
Updated help message format:
Commands (regular/duo): !bgrank/!duorank, !bgdaily/!duodaily, !bgweekly/!duoweekly, !peak/!duopeak, !stats/!duostats, !top/!duotop. Milestones: !8k through !21k [server]. Valid servers: NA, EU, AP
### Initial Channels
Bot now connects to specific channels by default:
- liihs
- haitahs
- beterbabbit
- slyders_hs
### Fun Commands
1. `!goodbot`
   MrDestructoid Just doing my job MrDestructoid
   - Simple response using Twitch emotes
   - No parameters needed
# Monetization Strategy
## Subscriber-Only Features
- Certain commands will be restricted to Twitch subscribers to incentivize subscriptions.
- Commands like `!peak`, `!stats`, and `!top` may be made subscriber-only due to their higher resource usage.
## Limited Command Usage for Non-Subscribers
- Non-subscribers will have a limited number of uses for certain commands per day or week.
- A quota system will be implemented to track and manage command usage for non-subscribers.
## Implementation Plan
1. **Subscriber Verification**:
   - Use Twitch's API to verify subscriber status before executing restricted commands.
2. **Usage Tracking**:
   - Implement a rate-limiting mechanism to track command usage per user.
   - Reset usage counters periodically (e.g., daily or weekly).
3. **User Communication**:
   - Provide clear feedback to users when they reach their usage limit.
   - Encourage subscriptions by highlighting the benefits of unlimited access.
## Cost Management
- Regularly monitor DynamoDB usage and costs.
- Consider using DynamoDB's on-demand capacity mode for cost efficiency with unpredictable traffic.
## Future Enhancements
- Explore additional monetization options, such as offering premium features or content for subscribers.
- Continuously evaluate user feedback to refine the monetization strategy and enhance user experience.
# Future Enhancements
## Batch Operations
### Batch Reading
- **Objective**: Improve query performance and reduce latency for fetching multiple records.
- **Implementation**: Use DynamoDB's `batch_get_item` to retrieve multiple player records in a single operation.
- **Primary Use Cases**:
  1. **Database Updates**:
     - Batch fetch existing player records to compare with new API data
     - Efficiently determine which records need updates by comparing current ratings and ranks
     - Reduce read operations during the 2-minute update cycle
     - Known primary keys from API response make this ideal for batch reading
  2. **Top Players Query**:
     - Batch read top player data across multiple servers
     - Support commands like `!bgtop` and `!duotop`
### Batch Writing
- **Objective**: Optimize database updates by reducing the number of API calls and improving cost efficiency.
- **Implementation**: Use DynamoDB's `batch_writer` to update multiple player records in a single operation.
- **Use Cases**:
  - Leaderboard updates: Batch write player data after comparing with existing records
  - Milestone tracking: Batch write milestone achievements
### Implementation Considerations
- **Error Handling**: 
  - Implement retry logic for unprocessed items
  - Handle partial batch failures gracefully
  - Log any discrepancies for monitoring
- **Batch Size Limits**: 
  - Read: Maximum 100 items per batch
  - Write: Maximum 25 items per batch
  - Implement chunking for larger datasets
- **Cost Optimization**: 
  - Monitor read/write capacity unit consumption
  - Track batch operation efficiency
  - Compare costs before and after implementation
### Timeline
1. **Phase 1 - Batch Reading for Updates**:
   - Implement batch reading in the update cycle first
   - This offers immediate benefits for the most frequent operation
   - Reduces comparison overhead with current database contents
2. **Phase 2 - Batch Writing**:
   - Add batch writing for database updates
   - Implement after batch reading is stable
3. **Phase 3 - Additional Use Cases**:
   - Extend batch operations to other features
   - Implement based on usage patterns and cost analysis
### Expected Benefits
- Reduced API calls during update cycles
- Lower DynamoDB costs through optimized read/write operations
- Improved update cycle performance
- Better scalability as player count grows
## Dynamic Channel Management
### Objective
- Dynamically manage the list of Twitch channels the bot joins by fetching from a DynamoDB table (`ChannelTable`).
- Ensure the bot can handle errors gracefully when joining channels.
### Implementation Plan
1. **Channel Fetching**:
   - Fetch the list of channels from the `ChannelTable` in DynamoDB every minute.
   - Use a scheduled task or an asynchronous loop to perform this operation.
2. **Error Handling**:
   - Implement error handling for scenarios where a channel does not exist or cannot be joined.
   - Log errors and continue processing other channels.
3. **Channel Management**:
   - Compare the fetched list with the currently joined channels.
   - Join new channels that are not already joined.
   - Leave channels that are no longer in the list.
4. **Integration with Discord**:
   - Ensure that updates to the `ChannelTable` via Discord commands are reflected in the bot's channel list within a minute.
### Implementation Steps
1. **Fetch Channels from DynamoDB**:
   - Use `boto3` to query the `ChannelTable` for the list of channels.
   - Handle any exceptions during the fetch operation.
2. **Update Joined Channels**:
   - Use TwitchIO's `join_channels` and `part_channels` methods to manage channel connections.
   - Implement logic to determine which channels to join or leave based on the fetched list.
3. **Error Handling**:
   - Log any errors encountered when joining or leaving channels.
   - Implement retry logic for transient errors.
4. **Scheduled Fetching**:
   - Use an asynchronous loop to fetch the channel list every minute.
   - Ensure the loop does not block other bot operations.
- Improved flexibility in managing the bot's channel connections.
- Reduced manual intervention for channel management.
- Enhanced integration with Discord for real-time updates.
1. **Phase 1 - Initial Implementation**:
   - Implement channel fetching and error handling.
   - Test with a small set of channels.
2. **Phase 2 - Full Deployment**:
   - Deploy the feature to production.
   - Monitor for any issues and optimize as needed.
3. **Phase 3 - Continuous Improvement**:
   - Gather feedback and make iterative improvements.
   - Explore additional features, such as notifying Discord of channel join/leave events.
## Channel Joining Optimization
### Prioritize Live Channels
- **Objective**: Optimize channel joining by prioritizing live channels to ensure the bot is active where needed.
- **Implementation**:
  1. **Fetch Live Channels**:
     - Use Twitch's `Get Streams` endpoint to identify live channels.
     - Prioritize these channels for joining.
  2. **Join Live Channels First**:
     - Use TwitchIO's `join_channels` method to join live channels first.
     - Join remaining channels afterward.
     - Log any errors during the joining process.
     - Retry joining failed channels if necessary.
### Benefits
1. **Resource Optimization**:
   - Focus resources on active channels.
   - Reduce unnecessary operations in offline channels.
2. **Performance**:
   - Faster engagement with live audiences.
   - Efficient use of API calls and bot resources.
1. **API Usage**:
   - Monitor API rate limits.
   - Implement caching to minimize API calls.
   - Handle API and joining errors gracefully.
   - Log status changes for monitoring.
3. **Status Updates**:
   - Regularly update channel status to reflect changes.
   - Maintain a list of live channels for prioritization.
## Command Aliases
### Regular Battlegrounds Commands
- Primary: `!rank`, `!day`, `!week`
- Aliases: `!bgrank`, `!bgdaily`, `!bgweekly`
### Duo Mode Commands
- Primary: `!duorank`
- Daily Stats:
  - Primary: `!duoday`
  - Alias: `!duodaily`
- Weekly Stats:
  - Primary: `!duoweek`
  - Alias: `!duoweekly`
1. **Command Registration**:
   ```python
   @commands.command(name="rank", aliases=["bgrank"])
   async def rank_command(self, ctx, ...):
       # Existing rank logic
   @commands.command(name="day", aliases=["bgdaily"])
   async def day_command(self, ctx, ...):
       # Existing daily logic
   @commands.command(name="week", aliases=["bgweekly"])
   async def week_command(self, ctx, ...):
       # Existing weekly logic
   @commands.command(name="duoday", aliases=["duodaily"])
   async def duo_day_command(self, ctx, ...):
       # Existing duo daily logic
   @commands.command(name="duoweek", aliases=["duoweekly"])
   async def duo_week_command(self, ctx, ...):
       # Existing duo weekly logic
2. **Help Command Updates**:
   - Update help messages to show both primary commands and aliases
   - Highlight shorter command names as preferred
   - Keep both versions working indefinitely for backward compatibility
   - No deprecation needed as both versions will remain supported
4. **Documentation**:
   - Update all documentation to show both options
   - List shorter versions first as preferred
   - Include examples using both naming conventions
1. **Improved User Experience**:
   - Shorter, more intuitive command names
   - Maintains familiarity for existing users
   - No disruption to existing workflows
2. **Consistency**:
   - Regular mode: `!rank`, `!day`, `!week`
   - Duo mode: `!duorank`, `!duoday`, `!duoweek`
   - Clear pattern between modes
3. **Flexibility**:
   - Users can choose their preferred command style
   - No forced migration
   - Both styles fully supported
## Performance Optimization
### Data Prefetching
1. **Top Players Prefetch**:
   - Fetch and cache top 100 players every 2 minutes
   - Store data for both regular and duo modes
   - Cache by server (NA, EU, AP)
   - Data to cache:
     - Player rankings
     - Current ratings
     - Daily/weekly progress
   - Benefits:
     - Faster response for `!rank`, `!top`, `!stats`
     - Reduced database load
     - Improved user experience
2. **Cache Management**:
   - Clear cache on new data fetch
   - Maintain separate caches for different game modes
   - Handle cache misses gracefully
   - Fall back to database queries when needed
### Command Usage Analytics
1. **Command Logging**:
   - Log each command invocation:
     - Command name
     - User who issued command
     - Channel where command was used
     - Timestamp
     - Arguments provided
     - Response time
     - Success/failure status
2. **Usage Metrics**:
   - Track:
     - Most used commands
     - Peak usage times
     - Common errors
     - Popular channels
     - Frequent users
   - Use data to:
     - Optimize caching strategy
     - Identify performance bottlenecks
     - Guide feature development
     - Monitor bot health
3. **Privacy Considerations**:
   - Store only necessary user data
   - Implement data retention policies
   - Ensure GDPR compliance
   - Allow users to opt out of tracking
### Implementation Priority
1. **Phase 1**: Command logging
   - Implement basic logging
   - Set up log analysis
   - Monitor command patterns
2. **Phase 2**: Top players prefetch
   - Implement caching system
   - Add background fetch task
   - Monitor performance impact
3. **Phase 3**: Optimization
   - Adjust cache timing based on usage
   - Expand cached data based on needs
   - Implement advanced analytics
## Help Command Enhancement

### Objective

- Provide detailed help information for each command.
- Allow users to request specific help using `!help <command>`.

### Implementation Plan

1. **Base Help Command**:
   - Update the base `!help` command to list all available commands.
   - Include instructions for using `!help <command>` to get detailed information.

2. **Specific Help Commands**:
   - Implement specific help responses for each command.
   - Provide detailed descriptions, usage examples, and any relevant notes.

3. **Command Descriptions**:
   - `!help rank`: Explain how to use the `!rank` command, including options for specifying players and servers.
   - `!help day`: Describe the `!day` command, detailing how to view daily stats.
   - `!help week`: Provide information on the `!week` command for weekly stats.
   - `!help peak`: Elaborate on the `!peak` command to view peak ratings.
   - `!help stats`: Explain the `!stats` command for server statistics.
   - `!help top`: Detail the `!top` command for viewing top players.

### User Communication

1. **Base Help Message**:
   - "Use `!help <command>` for detailed information on a specific command."
   - List all available commands with a brief description.

2. **Specific Help Responses**:
   - Provide clear, concise information tailored to each command.
   - Include examples of command usage.

### Expected Benefits

1. **Improved User Experience**:
   - Users can easily find detailed information about commands.
   - Reduces confusion and enhances usability.

2. **Increased Engagement**:
   - Encourages users to explore and use more commands.
   - Provides a self-service option for learning about bot features.

### Timeline

1. **Phase 1 - Base Help Command Update**:
   - Update the base help command to include instructions for specific help.

2. **Phase 2 - Implement Specific Help Commands**:
   - Develop detailed help responses for each command.
   - Test and refine based on user feedback.

3. **Phase 3 - Continuous Improvement**:
   - Gather user feedback to improve help content.
   - Update help information as new commands are added or existing ones are modified.