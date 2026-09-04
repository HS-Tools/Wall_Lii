#!/bin/bash
set -euo pipefail

git pull

# Keep the base-image and dependency layers cached. If a build fails, the
# currently running bots also remain available until a successful build.
docker build --pull=false -t hs_leaderboards_twitch -f ./twitch.Dockerfile .
docker build --pull=false -t hs_leaderboards_discord -f ./discord.Dockerfile .

# Remove only these containers after both images have built successfully so
# their old image references cannot block replacement.
docker rm -f hs_twitch hs_discord 2>/dev/null || true

docker run --restart unless-stopped -d \
  --name hs_twitch \
  -p 127.0.0.1:8787:8787 \
  hs_leaderboards_twitch

docker run --restart unless-stopped -d \
  --name hs_discord \
  hs_leaderboards_discord
