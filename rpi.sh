# Remove all images
docker rmi $(docker images -a -q)

docker build -t hs_leaderboards_twitch -f ./twitch.Dockerfile .
docker build -t hs_leaderboards_discord -f ./discord.Dockerfile .

# Kill all images after building updated ones
docker kill $(docker ps -q)
docker rm $(docker ps -a -q)

docker run -d hs_leaderboards_discord
docker run -d hs_leaderboards_twitch
