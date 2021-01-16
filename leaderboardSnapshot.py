from selenium import webdriver

option = webdriver.ChromeOptions()
option.add_argument('headless')
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

            rankCols = driver.find_elements_by_class_name('col-rank')
            tagCols = driver.find_elements_by_class_name('col-battletag')
            ratingCols = driver.find_elements_by_class_name('col-rating')

            for i in range(len(rankCols)):
                rank = rankCols[i].text
                tag = tagCols[i].text.encode('utf-8')
                rating = ratingCols[i].text
                
                ratingsDict[region][tag.lower()] = {'rank': rank, 'rating': rating}

    return ratingsDict
