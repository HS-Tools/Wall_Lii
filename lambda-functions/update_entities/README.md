# UpdateEntitiesFunction

This Lambda function automatically updates entity data from Hearthstone wiki sources when there are recent news posts.

## Purpose

The function checks for news posts created within the last 4 hours in the `news_posts` table. If recent posts are found, it scrapes and updates entity data from various Hearthstone Battlegrounds wiki pages.

## Schedule

- Runs every 4 hours via CloudWatch Events
- Only performs entity updates if recent news posts are detected

## Functionality

1. **News Check**: Queries the `news_posts` table for posts created within the last 4 hours
2. **Entity Update**: If recent posts exist, scrapes the following wiki sources:
   - Minions
   - Tavern Spells
   - Trinkets
   - Quests
   - Quest Rewards
   - Buddies
   - Heroes
   - Spells
   - Removed Cards
   - Anomalies

3. **Database Update**: Inserts or updates entity data in the `bg_entities` table

## Configuration

- **Timeout**: 900 seconds (15 minutes)
- **Memory**: 512 MB
- **Runtime**: Python 3.9

## Environment Variables

The function requires the following environment variables:
- `DB_HOST`: Database host
- `DB_PORT`: Database port (default: 5432)
- `DB_NAME`: Database name
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password

## Local Testing

Run the test script to verify functionality:

```bash
python test_local.py
```

## Deployment

The function is deployed as part of the SAM stack. Update the stack with:

```bash
sam build
sam deploy
```
