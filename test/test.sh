#!/bin/bash

echo "test blizzard leaderboard api call"
pipenv run python testApi.py
if [[ "$?" -ne 0 ]]; then
    exit "$?"
fi

echo "test leaderboard bot"
pipenv run python testLeaderboard.py
if [[ "$?" -ne 0 ]]; then
    exit "$?"
fi
