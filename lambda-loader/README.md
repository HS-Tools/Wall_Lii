# Migration Document for Loading Leaderboard Data via Lambda

## Current State

Currently all data is kept in memory and retrieved when Discord or Twitch events invoke the client.

It also seems that the fulfillment logic is mixed with the data storing logic in `leaderboardBot.py`. These parts should be decoupled for ease of us and maitenance, not to mention adding data persistence logic here would complicate this code further.

## Ideal State

We want to decouple the fetching and persistence of data from the bot fulfillment.

We will select one persistent data store from the following likely options:

- [Redis](https://aws.amazon.com/redis/)
- [DynamoDB](https://aws.amazon.com/dynamodb/)
- [Some managed SQL Database if we want to relate the data to other sources down the road.](https://aws.amazon.com/rds/)

I think Redis probably fits this use case best. Redis treats the data as ephemeral, and since we don't care about the data after 24 hours, I think this is the best fit.
