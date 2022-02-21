# Tests

## Testing Locally

This branch uses a local download of the dynamodb-local and an in memory database to make tests run quickly.

The tests are run against static leaderboard data from a [past season](https://playhearthstone.com/en-us/community/leaderboards/?region=US&leaderboardId=BG&seasonId=1).

### Requirements

- java
  - `brew install java` on a mac
- unzip
- curl

### Setup

1. download using `./scripts/download-dynamodb-local.sh`
2. run using `./scripts/run-dynamodb-local.sh dynamodb-local`
3. open a 2nd terminal

### Run Tests

```
pipenv install
cd test
pipenv run python testFile.py
```
