#!/usr/bin/env python3
import boto3
from datetime import datetime

def show_milestones(server=None, game_mode='0', season='1'):
    """Show milestone achievements"""
    ddb = boto3.resource(
        'dynamodb',
        endpoint_url='http://localhost:8000',
        region_name='us-east-1',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )
    
    table = ddb.Table('MilestoneTracking')
    
    # Build query parameters
    if server:
        key = f"{season}-{game_mode}-{server}"
        response = table.query(
            KeyConditionExpression='SeasonGameModeServer = :key',
            ExpressionAttributeValues={
                ':key': key
            }
        )
    else:
        # Scan for all servers
        response = table.scan()
    
    items = response.get('Items', [])
    
    print(f"\nMilestone Achievements{f' for {server}' if server else ''}:")
    print("-" * 80)
    print(f"{'Rating':<8} {'Player':<15} {'Server':<5} {'Date':<12} {'Exact Rating'}")
    print("-" * 80)
    
    for item in sorted(items, key=lambda x: (x['Milestone'], x['SeasonGameModeServer'])):
        timestamp = int(float(item['Timestamp']))
        date = datetime.fromtimestamp(timestamp).strftime('%B %d')
        server = item['SeasonGameModeServer'].split('-')[2]
        print(f"{item['Milestone']:<8} {item['PlayerName']:<15} {server:<5} {date:<12} {item['Rating']}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Show milestone achievements')
    parser.add_argument('--server', help='Filter by server (NA, EU, AP)')
    parser.add_argument('--mode', default='0', help='Game mode (0=BG, 1=Duo)')
    parser.add_argument('--season', default='1', help='Season number')
    args = parser.parse_args()
    
    show_milestones(args.server, args.mode, args.season) 