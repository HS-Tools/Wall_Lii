#!/bin/bash

set -e

echo "test blizzard leaderboard api call"
pipenv run python testApi.py

echo "test leaderboard bot"
pipenv run python testLeaderboard.py

