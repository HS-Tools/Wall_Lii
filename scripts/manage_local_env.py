#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time


def run_command(command, check=True):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            command, shell=True, check=check, capture_output=True, text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")
        print(f"Error: {e.stderr}")
        if check:
            sys.exit(1)
        return None


def setup_environment():
    """Setup local development environment"""
    print("\n1. Setting up environment variables...")
    os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:8000"
    os.environ["TABLE_NAME"] = "HearthstoneLeaderboard"


def start_services():
    """Start Docker services"""
    print("\n2. Starting Docker services...")
    try:
        # Check if services are already running
        result = run_command("docker ps | grep dynamodb-local", check=False)
        if result and "dynamodb-local" in result:
            print("DynamoDB is already running")
            return

        # Start DynamoDB
        run_command("docker-compose up -d dynamodb-local")
        time.sleep(2)  # Wait for services to start

        # Verify DynamoDB is running
        result = run_command("docker ps | grep dynamodb-local", check=False)
        if not result or "dynamodb-local" not in result:
            raise Exception("Failed to start DynamoDB")

    except Exception as e:
        print(f"Error starting services: {str(e)}")
        sys.exit(1)


def reset_database():
    """Reset and initialize the database"""
    print("\n3. Resetting database...")
    run_command("python scripts/init_local_db.py")
    time.sleep(2)  # Wait for table creation


def populate_data():
    """Populate database with current leaderboard data"""
    print("\n4. Populating database with current data...")
    run_command("python scripts/run_local_updater.py --once")


def verify_queries():
    """Verify all query access patterns"""
    print("\nVerifying query access patterns...")

    # 1. Direct query by GameModeServerPlayer
    print("\n1. Testing direct query...")
    result = run_command(
        """
        aws dynamodb query \
        --table-name HearthstoneLeaderboard \
        --key-condition-expression "GameModeServerPlayer = :gmsp" \
        --expression-attribute-values '{":gmsp": {"S": "0#NA#lii"}}' \
        --endpoint-url http://localhost:8000 \
        --no-cli-pager
    """
    )
    if '"Count": 1' in result:
        print("✓ Direct query successful")
    else:
        print("✗ Direct query failed")

    # 2. Query by rank using RankLookupIndex
    print("\n2. Testing rank lookup...")
    result = run_command(
        """
        aws dynamodb query \
        --table-name HearthstoneLeaderboard \
        --index-name RankLookupIndex \
        --key-condition-expression "GameModeServer = :gms AND CurrentRank = :rank" \
        --expression-attribute-values '{":gms": {"S": "0#NA"}, ":rank": {"N": "1"}}' \
        --endpoint-url http://localhost:8000 \
        --no-cli-pager
    """
    )
    if '"CurrentRank": {"N": "1"}' in result:
        print("✓ Rank lookup successful")
    else:
        print("✗ Rank lookup failed")

    # 3. Query by player using PlayerLookupIndex
    print("\n3. Testing player lookup...")
    result = run_command(
        """
        aws dynamodb query \
        --table-name HearthstoneLeaderboard \
        --index-name PlayerLookupIndex \
        --key-condition-expression "PlayerName = :name AND GameMode = :mode" \
        --expression-attribute-values '{":name": {"S": "lii"}, ":mode": {"S": "0"}}' \
        --endpoint-url http://localhost:8000 \
        --no-cli-pager
    """
    )
    if '"PlayerName": {"S": "lii"}' in result:
        print("✓ Player lookup successful")
    else:
        print("✗ Player lookup failed")


def verify_setup():
    """Verify the setup by running tests"""
    print("\n5. Verifying setup...")
    verify_queries()  # Add query verification
    run_command("python scripts/test_queries.py")


def stop_services():
    """Stop Docker services"""
    print("\nStopping Docker services...")
    try:
        run_command("docker-compose down")
    except Exception as e:
        print(f"Error stopping services: {str(e)}")
        # Don't exit, just warn


def cleanup_docker():
    """Clean up Docker resources"""
    print("\nCleaning up Docker resources...")
    try:
        # Stop and remove containers
        run_command("docker-compose down", check=False)
        run_command("docker rm -f dynamodb-local", check=False)

        # Remove volumes
        run_command("docker volume prune -f", check=False)

        # Remove any leftover data
        run_command("rm -rf .dynamodb", check=False)  # In case there's local data
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Manage local development environment")
    parser.add_argument(
        "command", choices=["setup", "start", "stop", "reset", "verify", "cleanup"]
    )
    parser.add_argument(
        "--skip-verify", action="store_true", help="Skip verification step"
    )

    args = parser.parse_args()

    if args.command == "setup":
        cleanup_docker()  # Clean up before setup
        setup_environment()
        start_services()
        reset_database()
        populate_data()
        if not args.skip_verify:
            verify_setup()
        print("\nSetup complete!")

    elif args.command == "start":
        setup_environment()
        start_services()
        print("\nServices started!")

    elif args.command == "stop":
        stop_services()
        print("\nServices stopped!")

    elif args.command == "reset":
        reset_database()
        populate_data()
        if not args.skip_verify:
            verify_setup()
        print("\nReset complete!")

    elif args.command == "verify":
        verify_setup()
        print("\nVerification complete!")
    elif args.command == "cleanup":
        cleanup_docker()
        print("\nCleanup complete!")


if __name__ == "__main__":
    main()
