#!/bin/bash

# Remove all images
git pull

docker system prune -f
docker rmi $(docker images -a -q)

docker build -t hs_leaderboards_twitch -f ./twitch.Dockerfile .
docker build -t hs_leaderboards_discord -f ./discord.Dockerfile .

# Kill all images after building updated ones
docker kill $(docker ps -q)
docker rm $(docker ps -a -q)

# Create logs directory if it doesn't exist
mkdir -p /home/jim/Wall_Lii/logs

# Run containers with volume mounts
docker run --restart always -d \
  -v /home/jim/Wall_Lii/logs:/logs \
  --name hs_twitch \
  hs_leaderboards_twitch

docker run --restart always -d \
  --name hs_discord \
  hs_leaderboards_discord
