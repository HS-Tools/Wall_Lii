#!/bin/bash

# --- CONFIG ---

# after putting this in server, create a cron
# 1. crontab -e
# 2. */5 * * * * /home/jim/check_bot_helix.sh >> /home/jim/bot_monitor.log 2>&1

CHANNEL_ID="73626243"     # e.g. 123456789 for liihs
BOT_LOGIN="walliibot"                 # all lowercase
CLIENT_ID="" # fill this in from https://twitchtokengenerator.com/
USER_TOKEN="" # fill this in with moderator:read:chatters scope
RESTART_CMD="cd Wall_Lii && sh start.sh"

# --- DO NOT EDIT BELOW THIS LINE (unless you want to tweak parsing) ---

# Call Helix Get Chatters
JSON=$(curl -s -X GET "https://api.twitch.tv/helix/chat/chatters?broadcaster_id=${CHANNEL_ID}&moderator_id=${CHANNEL_ID}&first=1000" \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Client-Id: ${CLIENT_ID}")

# Optional: log raw JSON on failure to debug auth issues
if [ -z "$JSON" ]; then
  echo "$(date): Empty response from Helix /chat/chatters" >&2
fi

# Check if BOT_LOGIN appears in the user_login fields
if echo "$JSON" | grep -qi "\"user_login\":\"${BOT_LOGIN}\""; then
  echo "$(date): ${BOT_LOGIN} present in chat."
else
  echo "$(date): ${BOT_LOGIN} NOT present in chat. Restarting..."
  eval "$RESTART_CMD"
fi