# utils/aws_dynamo_utils.py
import os
import boto3
import logging

logger = logging.getLogger(__name__)


class DynamoDBClient:
    def __init__(self):
        aws_kwargs = {
            "region_name": "us-east-1",
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        }

        logger.info(
            f"AWS credentials present: {bool(aws_kwargs['aws_access_key_id'] and aws_kwargs['aws_secret_access_key'])}"
        )

        self.dynamodb = boto3.resource("dynamodb", **aws_kwargs)

        self.alias_table = self.dynamodb.Table("player-alias-table")
        self.channel_table = self.dynamodb.Table("channel-table")

        self._test_table_connection(self.alias_table, "alias table")
        self._test_table_connection(self.channel_table, "channel table")

    def _test_table_connection(self, table, name):
        try:
            table.table_status
            logger.info(f"Successfully connected to {name}")
        except Exception as e:
            logger.error(f"Failed to connect to {name}: {e}")

    # ---------- Alias Table ----------
    def add_alias(self, alias, player_name):
        try:
            self.alias_table.put_item(Item={"Alias": alias, "PlayerName": player_name})
            return f"Alias {alias} added for {player_name}"
        except Exception as e:
            logger.error(f"Error adding alias: {e}")
            return f"Error adding alias: {e}"

    def delete_alias(self, alias):
        try:
            self.alias_table.delete_item(Key={"Alias": alias})
            return f"Alias {alias} deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting alias: {e}")
            return f"Error deleting alias: {e}"

    # ---------- Channel Table ----------
    def add_channel(self, channel, player_name=None):
        try:
            player_name = player_name or channel
            self.channel_table.put_item(
                Item={"ChannelName": channel, "PlayerName": player_name}
            )
            return f"Channel {channel} added successfully with the player_name:{player_name}"
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return f"Error adding channel: {e}"

    def delete_channel(self, channel):
        try:
            self.channel_table.delete_item(Key={"ChannelName": channel})
            return f"Channel {channel} deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            return f"Error deleting channel: {e}"
