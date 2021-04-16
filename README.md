# HS-BG-Leaderboards-Bot
Fetches Hearthstone Battlegrounds Leaderboard information every 3 minutes to enable users to get the current rank of a player and to fetch their daily record of games.

# Commands:
* !bgrank {battletag}: Gets the rank and mmr of a player in their highest rated region
* !bgdaily {battletag}: Gets the starting mmr, current mmr and the list of mmr changes from all games played during the day. This resets at midnight PST time
* !wall_lii: Help command
* !goodbot: Praise the bot

# Webscraping with chromium:
This project was initially done by scraping the hearthstone leaderboards with chromium. I have since changed to using the official api due to excessive resource requirements that my raspberry pi could not support. The following instructions are for using leaderboardSnapshot.py

# How to run:
1. Download Chrome
2. Download Chromedriver https://chromedriver.chromium.org/downloads
3. Put Chromedriver in PATH
4. Download pipenv and populate .env
5. Run with ```pipenv run python app.py```

# RPI specific stuff:
1. Follow instructions here to set up chromedriver: https://www.reddit.com/r/selenium/comments/7341wt/success_how_to_run_selenium_chrome_webdriver_on/
2. Follow instructions here to add new option: https://www.raspberrypi.org/forums/viewtopic.php?f=66&t=258019&view=unread&sid=c63996b8d86958dfb501cf3e5b04e3e0#p1575053
