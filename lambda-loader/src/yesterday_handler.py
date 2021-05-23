import api
import data
import os
import boto3

MAIN_TABLE_NAME = os.environ.get('TABLE_NAME')
YESTERDAY_TABLE_NAME = os.environ.get('YESTERDAY_TABLE_NAME')

def handler(event, context):
    resource = boto3.resource('dynamodb')

    today_table = resource.Table(MAIN_TABLE_NAME)
    yesterday_table = resource.Table(YESTERDAY_TABLE_NAME)

    yesterday_scan = yesterday_table.scan()

    # Delete the entire yesterday table
    with yesterday_table.batch_writer() as batch:
        for each in yesterday_scan['Items']:
            batch.delete_item(
                Key = {
                    'PlayerName': each['PlayerName'],
                    'Region': each['Region']
                }
            )

    today_scan = today_table.scan()

    # Move today's table to yesterday
    with yesterday_table.batch_writer() as batch:
        for each in today_scan['Items']:
            if 'TTL' in each.keys():
                del each['TTL']
            batch.put_item(each)
