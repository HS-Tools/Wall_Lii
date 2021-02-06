from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

option = webdriver.ChromeOptions()
option.add_argument('headless')
option.add_argument('--disable-features=VizDisplayCompositor')
driver = webdriver.Chrome(options=option)
baseUrl = 'https://playhearthstone.com/en-us/community/leaderboards/'

currentSeason = 2
pages = range(1, 9) 
regions = ['US', 'EU', 'AP']
ratingsDict = {region : {} for region in regions}

def getLeaderboardSnapshot():
    ratingsDict = {region : {} for region in regions}

    for region in regions:
        for page in pages:
            url = baseUrl + '?region=' + region + '&leaderboardId=BG&seasonId=' \
            + str(currentSeason) + '&page=' + str(page)

            driver.get(url)

            try:
                rankCols = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "col-rank"))
                )
                tagCols = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "col-battletag"))
                )
                ratingCols = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "col-rating"))
                )
                for i in range(len(rankCols)):
                    rank = rankCols[i].text
                    tag = tagCols[i].text.encode('utf-8')
                    rating = ratingCols[i].text
                    
                    ratingsDict[region][tag.lower()] = {'rank': rank, 'rating': rating}
            except:
                print('Web driver timed out')
                return None

            # rankCols = driver.find_elements_by_class_name('col-rank')
            # tagCols = driver.find_elements_by_class_name('col-battletag')
            # ratingCols = driver.find_elements_by_class_name('col-rating')

    return ratingsDict
