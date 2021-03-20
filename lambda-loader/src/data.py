import boto3
import os
import time
from datetime import datetime, date, timedelta
from datetime import time as dtime
from pytz import timezone

'''
RankingDatabaseClient provides a wrapper for interacting with DyanmoDB and Player objects therein.

This class provides two external APIs, get_item and put_item. Both requiring a Partition and Sort Key value for lookups or updates to be performed.

Ideally this class would be refactored to use DynamoDB's batch APIs due to the bursty nature of this workflow.
'''
class RankingDatabaseClient:

    def __init__(self,table):
        resource = boto3.resource('dynamodb')
        self.table = resource.Table(table)
    '''
    TODO pydoc TTL
    '''
    def get_item(self,region,player,region_name="Region",player_name="PlayerName",rating_name="Ratings", ttl_name="TTL"):
        try:
            response = self.table.get_item(Key={
                region_name:region,
                player_name:player
            })
            print(f"{response} fetched from DDB")
            time.sleep(.01)
            return response['Item']
        except Exception as e:
            print(e)

            print(f"{player} was not fetched and is being created now")

            return {
                region_name:region,
                player_name:player,
                ttl_name: self.__getMidnightTTL(),
                rating_name:[]
            }

    '''
    TODO pydoc
    '''
    def put_item(self,region,player,rating,region_name="Region",player_name="PlayerName"):
        item = self.get_item(region,player,region_name,player_name)
        rating = int(rating)
        item = self.__append_rating_to_list(rating,item)
        self.table.put_item(Item=item)

    '''
    This almost certainly won't work.

    The object probably looks something like this:
    {
        region_name:'NA',
        player_name:'lii',
        ranks:{'L':[{'N':15000} ... ]}
    }

    TODO pydoc
    '''
    def __append_rating_to_list(self,rating,item):
        if type(rating) != int:
            raise Exception("Rating:",rating,"was expected to be of type int, but was type",type(rating),".")

        if 'Ratings' not in item or type(item['Ratings']) is not list: # Key check and type check.
            item['Ratings'] = []

        if item['Ratings'] and item['Ratings'][-1] == rating: # List is not empty and No updates to ratings list, return.
            return item 

        item['Ratings'].append(rating)

        print(f"{item} was appended on")
        return item # Return isn't strictly neccessary, but it is nice for readability.

    def __getMidnightTTL(self):
        tz = timezone('US/Pacific')
        tomorrow = date.today() + datetime.timedelta(days=1)
        midnight_without_tzinfo = datetime.combine(tomorrow, dtime())
        midnight_with_tzinfo = tz.localize(midnight_without_tzinfo)
        midnight_as_epoch = int(midnight_with_tzinfo.timestamp())

        return midnight_as_epoch + 86400

