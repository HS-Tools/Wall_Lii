#!/usr/bin/env python3
import boto3
import time
import subprocess
import os
from pathlib import Path

def archive_season(old_season, new_season):
    """Handle full season transition"""
    ddb = boto3.client('dynamodb', region_name='us-east-1')
    
    print(f"Starting season transition from {old_season} to {new_season}...")
    
    # 1. Check if old table exists and backup if it does
    try:
        # Check if table exists
        try:
            ddb.describe_table(TableName='HearthstoneLeaderboardV2')
            table_exists = True
        except ddb.exceptions.ResourceNotFoundException:
            print("\nTable HearthstoneLeaderboardV2 not found, skipping backup")
            table_exists = False
        
        if table_exists:
            print("\nBacking up old table...")
            # Create backup
            backup_name = f"HearthstoneLeaderboardV2-Season{old_season}-Backup"
            ddb.create_backup(
                TableName='HearthstoneLeaderboardV2',
                BackupName=backup_name
            )
            print(f"Created backup: {backup_name}")
            
            # Wait for backup to complete
            print("Waiting for backup to complete...")
            time.sleep(30)
            
            # Delete original table
            ddb.delete_table(TableName='HearthstoneLeaderboardV2')
            print("Deleted original table")
            
            # Wait for deletion
            print("Waiting for deletion to complete...")
            time.sleep(30)
            
    except Exception as e:
        print(f"Error handling table backup/deletion: {e}")
        return
    
    # 2. Deploy new infrastructure
    print("\nDeploying new infrastructure...")
    try:
        # Get path to lambda directory
        script_dir = Path(__file__).parent
        lambda_dir = script_dir.parent / 'lambda-loader'
        
        # Change to lambda directory and deploy
        os.chdir(lambda_dir)
        subprocess.run(['sam', 'build'], check=True)
        subprocess.run(['sam', 'deploy'], check=True)
        print("Infrastructure deployed")
    except Exception as e:
        print(f"Error deploying: {e}")
        return
    
    print("\nSeason transition complete!")
    if table_exists:
        print(f"- Old table backed up as: {backup_name}")
    print(f"- New table created as: HearthstoneLeaderboardV2")
    print(f"- Lambda updated for season {new_season}")
    print("\nPlease verify:")
    print("1. New table is empty and ready")
    print("2. Lambda is using correct season number")
    if table_exists:
        print("3. Backup is accessible for historical data")

if __name__ == "__main__":
    archive_season('13', '14') 