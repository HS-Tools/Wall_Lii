import os
import json
import re
import requests
import time
import psycopg2
from requests.exceptions import HTTPError
from logger import setup_logger

# Set up logger
logger = setup_logger("twitch_live_check")


def chunked(iterable, size):
    """Split an iterable into chunks of specified size"""
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def get_db_connection():
    """Get PostgreSQL connection using environment variables"""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        sslmode="require",
    )


def get_twitch_token():
    """Get Twitch OAuth token for API access"""
    client_id = os.environ.get("TWITCH_LIVE_CHECK_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_LIVE_CHECK_SECRET")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "Environment variables TWITCH_LIVE_CHECK_CLIENT_ID and TWITCH_LIVE_CHECK_SECRET must be set"
        )

    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
    )

    try:
        resp.raise_for_status()
    except HTTPError:
        try:
            error_info = resp.json()
        except ValueError:
            error_info = {"error": resp.text}
        raise RuntimeError(
            f"Twitch token request failed (status {resp.status_code}): {error_info}"
        )

    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"No access_token in response: {data}")

    return data["access_token"]


def fetch_live_channels(channels, token):
    """Fetch live channels from Twitch API"""
    valid_pattern = re.compile(r"^[0-9A-Za-z_]{4,25}$")
    channels = [c for c in channels if valid_pattern.match(c)]

    headers = {
        "Client-ID": os.environ.get("TWITCH_LIVE_CHECK_CLIENT_ID"),
        "Authorization": f"Bearer {token}",
    }

    live = set()
    for batch in chunked(channels, 100):
        params = [("user_login", name) for name in batch]
        try:
            resp = requests.get(
                "https://api.twitch.tv/helix/streams",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for stream in data:
                live.add(stream["user_login"])
        except HTTPError as e:
            logger.error(f"Error fetching batch {batch}: {e}")

        time.sleep(0.5)  # avoid rate limits

    return live


def update_live_flags():
    """Update live flags for all channels in the database"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch all channel names
        cur.execute("SELECT channel FROM channels")
        rows = cur.fetchall()
        all_channels = [r[0] for r in rows]

        logger.info(f"Checking {len(all_channels)} channels for live status")

        # Get Twitch token and fetch live channels
        token = get_twitch_token()
        live_channels = fetch_live_channels(all_channels, token)

        logger.info(
            f"Found {len(live_channels)} live channels: {', '.join(live_channels)}"
        )

        # Update live flag for each channel
        cur.execute("UPDATE channels SET live = FALSE")
        for channel in live_channels:
            cur.execute(
                "UPDATE channels SET live = TRUE WHERE channel = %s", (channel,)
            )

        conn.commit()

        return {
            "total_channels": len(all_channels),
            "live_channels": len(live_channels),
            "live_channel_list": list(live_channels),
        }

    except Exception as e:
        logger.error(f"Error updating live flags: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cur.close()
            conn.close()


def lambda_handler(event, context):
    """AWS Lambda entry point"""
    try:
        result = update_live_flags()
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Live channel check completed successfully", "data": result}
            ),
        }
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error during execution: {str(e)}"}),
        }


if __name__ == "__main__":
    # For local testing
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
