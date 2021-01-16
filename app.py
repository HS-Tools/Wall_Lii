from leaderboardSnapshot import getLeaderboardSnapshot
import threading
import time
import schedule

regions = ['US', 'EU', 'AP']
currentLeaderboard = {}

def updateDict():
    global currentLeaderboard

    currentLeaderboard = getLeaderboardSnapshot()
    print('Finished fetching leaderboard')

def updateThreaded():
    thread = threading.Thread(target=updateDict)
    thread.start()

def getResponseText(tag):
    global regions
    global currentLeaderboard

    highestRank = 9999
    encodedTag = tag.encode('utf-8')
    text = "{} is not on any BG leaderboards".format(tag)
    for region in regions:
        if encodedTag in currentLeaderboard[region]:
            rank = currentLeaderboard[region][encodedTag]['rank']
            rating = currentLeaderboard[region][encodedTag]['rating']

            if int(rank) < highestRank:
                highestRank = int(rank)
                text = "{} is rank {} in {} with {} mmr" \
                .format(tag, rank, region, rating)

    return text

# Get leaderboards on start
updateDict()

tag = ''
schedule.every(10).minutes.do(updateThreaded)

while tag != "exit":
    schedule.run_pending()
    time.sleep(1)
    tag = input("Enter tag: ")
    print(getResponseText(tag))