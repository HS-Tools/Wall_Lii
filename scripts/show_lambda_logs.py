import boto3
from datetime import datetime, timedelta

def show_milestone_logs():
    """Show recent Lambda logs related to milestones"""
    logs = boto3.client('logs', region_name='us-east-1')
    
    log_group = '/aws/lambda/hearthstone-leaderboard-stack-LeaderboardUpdaterFunction'
    
    # Get logs from last hour
    start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    end_time = int(datetime.now().timestamp() * 1000)
    
    try:
        response = logs.filter_log_events(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            filterPattern='milestone'
        )
        
        for event in response['events']:
            print(event['message'])
            
    except Exception as e:
        print(f"Error getting logs: {str(e)}")

if __name__ == "__main__":
    show_milestone_logs() 