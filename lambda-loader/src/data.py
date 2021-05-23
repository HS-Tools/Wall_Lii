import boto3
from boto3.dynamodb.conditions import Key, Attr
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
    def __init__(self, **kargs):
        self.table_name = os.environ['TABLE_NAME'];
        self.resource = boto3.resource('dynamodb', **kargs)
        self.client = boto3.client('dynamodb', **kargs)
        self.table = self.resource.Table( self.table_name )

    def create_table(self, table_name=None):
        if table_name is None:
            table_name = self.table_name
        # print("creating table")
        self.table = self.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'PlayerName', 'KeyType': 'HASH'},
                {'AttributeName': 'Region', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PlayerName', 'AttributeType': 'S'},
                {'AttributeName': 'Region', 'AttributeType': 'S'},
                {'AttributeName': 'Rank', 'AttributeType': 'N'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'PlayerRank',
                    'KeySchema': [
                        {'AttributeName': 'Rank', 'KeyType': 'HASH'},
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL',
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 2,
                        'WriteCapacityUnits': 2,
                    },
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10,
            },
            BillingMode='PROVISIONED',
        )

    def default_entry(self, region, player, rank=-1, rating=1, region_name="Region",player_name="PlayerName",rating_name="Ratings", ttl_name="TTL", rank_name="Rank"):
        return {
            player_name:player,
            region_name:region,
            ttl_name: self.__getMidnightTTL(),
            rating_name:[rating],
            rank_name: rank
        }
    '''
    TODO pydoc TTL
    '''
    def clear_ranks(self, region, keep_players, region_name="Region",player_name="PlayerName",rating_name="Ratings", ttl_name="TTL", rank_name="Rank"):
        response = self.table.scan(
            Select = 'ALL_ATTRIBUTES',
            FilterExpression= (~Key(rank_name).eq(-1)) and Key(region_name).eq(region),
        )
        with self.table.batch_writer() as batch:
            for item in response['Items']:
                if (item[player_name] not in keep_players):
                    item[rank_name] = -1
                    batch.put_item(Item=item)

    '''
    TODO pydoc TTL
    '''
    def get_item(self,region,player,region_name="Region",player_name="PlayerName",rating_name="Ratings", ttl_name="TTL", rank_name="Rank"):
        try:
            response = self.table.get_item(Key={
                player_name:player,
                region_name:region,
            })
            return response['Item']
        except Exception as e:
            return self.default_entry(region=region, player=player)
    '''
    TODO pydoc
    '''
    def put_item(self,region,player,rating,rank,lastUpdate,region_name="Region",player_name="PlayerName"):
        item = self.get_item(region,player,region_name,player_name)
        item['LastUpdate'] = lastUpdate
        rating = int(rating)
        put = self.__append_rating_to_list(rating,item)
        if (put) or item['Rank'] != rank:
            item['Rank'] = rank
            self.table.put_item(Item=item)

    '''
    TODO pydoc
    '''
    def put_items(self, region, data, region_name="Region", player_name="PlayerName", rating_name="Ratings", ttl_name="TTL", rank_name="Rank"):
        response = self.table.scan(
            Select = 'ALL_ATTRIBUTES',
            FilterExpression= Key(region_name).eq(region),
        )
        items = []
        players = list(data.keys())
        if 'Items' in response.keys():
            items = response['Items']
        for item in items:
            player = item[player_name]
            if player in players:

                update_rating = self.__append_rating_to_list( rating=data[player]['rating'], item=item)
                if update_rating or item[rank_name] != data[player]['rank']:
                    item[rank_name] = data[player]['rank']
                else:
                    items.remove(item) ## no changes so don't write again
                players.remove(player)
            else:
                if item[rank_name] == -1:
                    items.remove(item) ## no changes so don't write again
                else:
                    item[rank_name] = -1
        for player in players:
            items.append(self.default_entry(
                region=region,
                player=player,
                rank=data[player]['rank'],
                rating=data[player]['rating'] )
            )

        with self.table.batch_writer() as batch:
            for item in response['Items']:
                batch.put_item(Item=item)


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
            return False

        item['Ratings'].append(rating)

        return True

    def __getMidnightTTL(self):
        tz = timezone('US/Pacific')
        today = date.today()
        midnight_without_tzinfo = datetime.combine(today, dtime())
        midnight_with_tzinfo = tz.localize(midnight_without_tzinfo)
        midnight_as_epoch = int(midnight_with_tzinfo.timestamp())

        return midnight_as_epoch + 86400

