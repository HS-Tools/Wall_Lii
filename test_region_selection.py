from leaderboardBot import LeaderBoardBot
import threading
from time import sleep

bot = LeaderBoardBot()
leaderboardThread = threading.Thread(target=bot.updateDict)
leaderboardThread.setDaemon(True)
leaderboardThread.start()
sleep(3)
param_sets = [
    ['sleepy'],
    ['sleepy','Europe'],
    ['sleepy', 'EU'],
    ['sleepy','NA'],
    ['sleepy', 'AP'],
    ['sleepy','bogus_region']
]

for param_set in param_sets:
    print(f"Params: {param_set}")
    print(bot.getRankText(*param_set))

