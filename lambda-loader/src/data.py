import boto3
import os
import time
import getMidnight
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
    def get_item(self,region,player,region_name="Region",player_name="PlayerName",rating_name="Ratings", ttl_name="ttl"):
        try:
            response = self.table.get_item(Key={
                region_name:region,
                player_name:player
            })
            time.sleep(.01)
            return response['Item']
        except Exception as e:
            print(e)
            return {
                region_name:region,
                player_name:player,
                ttl_name: getMidnight.getMidnightTTL(),
                rating_name:[]
            }

    '''
    TODO pydoc
    '''
    def put_item(self,region,player,rating,region_name="Region",player_name="PlayerName"):
        item = self.get_item(region,player,region_name,player_name)
        rating = int(rating)
        item = self._append_rating_to_list(rating,item)
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
    def _append_rating_to_list(self,rating,item):
        if 'Ratings' in item.keys():
            if len(item['Ratings']) > 0 and item['Ratings'][-1] != rating:
                item['Ratings'].append(rating) 
        else:
            item['Ratings'] = [rating]
        return item

