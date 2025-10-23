import os
from utils.db_utils import get_db_connection
from datetime import datetime


def add_channel(channel, player, youtube="", live=False):
    channel = channel.lower()
    player = player.lower()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO channels (channel, player, youtube, live, added_at)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (channel) DO UPDATE SET player=EXCLUDED.player, youtube=EXCLUDED.youtube, live=EXCLUDED.live
                    """,
                    (channel, player, youtube, live, datetime.now()),
                )
        return f"Channel {channel} added/updated successfully with the player name: {player}"
    except Exception as e:
        return f"Error adding channel: {e}"
    finally:
        conn.close()


def update_player(channel, player):
    channel = channel.lower()
    player = player.lower()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # Try to update the player column only
                cur.execute(
                    "UPDATE channels SET player = %s WHERE channel = %s",
                    (player, channel),
                )
                if cur.rowcount == 0:
                    # If no rows were updated, insert a new row with current timestamp
                    cur.execute(
                        """INSERT INTO channels (channel, player, added_at)
                               VALUES (%s, %s, %s)
                               ON CONFLICT (channel) DO NOTHING
                        """,
                        (channel, player, datetime.utcnow()),
                    )
        return f"Player for channel {channel} set to {player}"
    except Exception as e:
        return f"Error updating player for channel: {e}"
    finally:
        conn.close()


def delete_channel(channel):
    channel = channel.lower()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM channels WHERE channel = %s", (channel,))
        return f"Channel {channel} deleted successfully"
    except Exception as e:
        return f"Error deleting channel: {e}"
    finally:
        conn.close()


def get_all_live_channels():
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT channel FROM channels WHERE live = TRUE")
                return {row[0].strip().lower() for row in cur.fetchall()}
    except Exception as e:
        return {"liihs"}
    finally:
        conn.close()


def update_youtube(channel, youtube):
    channel = channel.lower()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # Try to update the youtube column only
                cur.execute(
                    "UPDATE channels SET youtube = %s WHERE channel = %s",
                    (youtube, channel),
                )
                if cur.rowcount == 0:
                    # If no rows were updated, insert a new row with current timestamp
                    cur.execute(
                        """INSERT INTO channels (channel, youtube, added_at)
                               VALUES (%s, %s, %s)
                               ON CONFLICT (channel) DO NOTHING
                        """,
                        (channel, youtube, datetime.utcnow()),
                    )
        return f"YouTube channel for {channel} set to {youtube}"
    except Exception as e:
        return f"Error updating YouTube channel: {e}"
    finally:
        conn.close()


def get_all_channels():
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT channel FROM channels")
                return {row[0].strip().lower() for row in cur.fetchall()}
    except Exception as e:
        return {"liihs"}
    finally:
        conn.close()
