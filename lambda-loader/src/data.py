import boto3
import os
import time
from datetime import datetime, date
from datetime import time as dtime
from pytz import timezone

'''
RankingDatabaseClient provides a wrapper for interacting with DyanmoDB and Player objects therein.

This class provides two external APIs, get_item and put_item. Both requiring a Partition and Sort Key value for lookups or updates to be performed.

Ideally this class would be refactored to use DynamoDB's batch APIs due to the bursty nature of this workflow.
'''
class RankingDatabaseClient:
    def __init__(self, url=None):
        self.table_name = os.environ['TABLE_NAME'];
        self.resource = None
        if url is not None:
            self.resource = boto3.resource('dynamodb',
                aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                region_name=os.environ['REGION'],
                endpoint_url=url)
        else:
            self.resource = boto3.resource('dynamodb')
        self.table = self.resource.Table( self.table_name )

    def create_table(self):
        print("creating table")
        self.table = self.resource.create_table(
            TableName=self.table_name,
            KeySchema=[
                {'AttributeName': 'PlayerName', 'KeyType': 'HASH'},
                {'AttributeName': 'Region', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PlayerName', 'AttributeType': 'S'},
                {'AttributeName': 'Region', 'AttributeType': 'S'},
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 25,
            },
            BillingMode='PROVISIONED',
        )
    '''
    TODO pydoc TTL
    '''
    def get_item(self,region,player,region_name="Region",player_name="PlayerName",rating_name="Ratings", ttl_name="TTL", rank_name="Rank"):
        try:
            response = self.table.get_item(Key={
                player_name:player,
                region_name:region,
            })
            time.sleep(.01)
            return response['Item']
        except Exception as e:
            print(e)

            return {
                player_name:player,
                region_name:region,
                ttl_name: self.__getMidnightTTL(),
                rating_name:[],
                rank_name: -1
            }

    '''
    TODO pydoc
    '''
    def put_item(self,region,player,rating,rank,lastUpdate,region_name="Region",player_name="PlayerName"):
        item = self.get_item(region,player,region_name,player_name)

        # To get only the time in 24 hour format.
        currentTimeUTC = str(datetime.utcnow())

        try:
            if (lastUpdate > item['LastUpdate']):
                item['LastUpdate'] = lastUpdate
            else:
                item['LastUpdate'] = currentTimeUTC
        except:
            print("CurrentTime was not found ")
            item['LastUpdate'] = currentTimeUTC

        rating = int(rating)
        item['Rank'] = rank
        item = self.__append_rating_to_list(rating,item)
        print(item)
        print(self.table.key_schema)
        self.table.put_item(Item=item)

    '''
    This almost certainly won't work.

    The object probably looks something like this:
    {
        region_name:'NA',
        player_name:'lii',
        rank: 1,
        Ratings:{'L':[{'N':15000} ... ]}
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

        return item # Return isn't strictly neccessary, but it is nice for readability.

    def __getMidnightTTL(self):
        tz = timezone('US/Pacific')
        today = date.today()
        midnight_without_tzinfo = datetime.combine(today, dtime())
        midnight_with_tzinfo = tz.localize(midnight_without_tzinfo)
        midnight_as_epoch = int(midnight_with_tzinfo.timestamp())

        return midnight_as_epoch + 86400

