import os
import aiocron
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import time
import json
import boto3
from boto3.dynamodb.conditions import Key
import requests
from discord import channel
import pytz
from supabase import create_client

from logger import setup_logger
from parseRegion import parseServer

logger = setup_logger("leaderboard_queries")

VALID_SERVERS = {"NA", "EU", "AP"}


class LeaderboardDB:
    def __init__(self, use_local=False, table_name="HearthstoneLeaderboard", useTestTimestamp=False):
        """Initialize DB connection
        
        Args:
            use_local (bool): If True, uses local DynamoDB tables. If False, uses AWS tables.
            table_name (str): Name of the leaderboard table
            useTestTimestamp (bool): If True, uses fixed timestamp for current time
        """
        if use_local:
            # Configure local DynamoDB client
            local_kwargs = {
                "endpoint_url": "http://localhost:8000",
                "region_name": "local",
                "aws_access_key_id": "dummy",
                "aws_secret_access_key": "dummy"
            }
            logger.info("Using local DynamoDB tables")
            self.dynamodb = boto3.resource("dynamodb", **local_kwargs)
            self.table = self.dynamodb.Table("leaderboard")
            self.alias_table = self.dynamodb.Table("alias")
            self.channel_table = self.dynamodb.Table("channel-table")
        else:
            # Configure AWS client for alias table (always use AWS)
            aws_kwargs = {
                "region_name": "us-east-1",
                "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            }

            logger.info(
                f"AWS credentials present: {bool(aws_kwargs['aws_access_key_id'] and aws_kwargs['aws_secret_access_key'])}"
            )

            # Initialize DynamoDB resource without endpoint_url
            self.dynamodb = boto3.resource("dynamodb", **aws_kwargs)
            self.table = self.dynamodb.Table(table_name)

            # Alias table always uses AWS connection
            aws_dynamodb = boto3.resource("dynamodb", **aws_kwargs)
            self.alias_table = aws_dynamodb.Table("player-alias-table")

            # Channel table always uses AWS connection
            self.channel_table = aws_dynamodb.Table("channel-table")

            # Test alias table connection
            try:
                self.alias_table.table_status
                logger.info("Successfully connected to alias table")
            except Exception as e:
                logger.error(f"Failed to connect to alias table: {e}")

            # Test channel table connection
            try:
                self.channel_table.table_status
                logger.info("Successfully connected to channel table")
            except Exception as e:
                logger.error(f"Failed to connect to channel table: {e}")

        if useTestTimestamp:
            self.useTestTimestamp = True
            # This is a fixed timestamp that is used for test_leaderboard_queries
            self.testTimestamp = datetime(2024, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
        else:
            self.useTestTimestamp = False

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        self.supabase = create_client(url, key)

        # Load aliases
        self.aliases = self._load_aliases()
        self.patch_link = "Currently fetching patch link..."
        logger.info(f"Initialized with {len(self.aliases)} aliases")
        
        # Set up cron job to update aliases every minute
        self.cron = aiocron.crontab("*/1 * * * *", func=self.update_aliases)
        self.fetch_patch_link_cron = aiocron.crontab('* * * * *', func=self.fetchPatchLink)

        self.update_daily_leaderboards()

    def update_daily_leaderboards(self, top_n: int = 10):
        """Updates the daily leaderboards in Supabase."""
        logger.info("Starting daily leaderboards update...")
        
        # Get today's date in LA timezone
        la_tz = pytz.timezone("America/Los_Angeles")
        utc_now = datetime.now(timezone.utc) if not self.useTestTimestamp else self.testTimestamp
        la_now = utc_now.astimezone(la_tz)
        today = la_now.date()
        
        # Initialize containers for each category
        climbers = []
        unluckiest = []
        grinders = []
        highest_rated = []
        
        try:
            # Scan DynamoDB for all players
            for server in VALID_SERVERS:
                logger.info(f"Processing server: {server}")
                game_mode_server = f"0#{server}"  # game_mode 0 for regular BG
                    
                response = self.table.scan(
                    FilterExpression="GameModeServer = :gms",
                    ExpressionAttributeValues={":gms": game_mode_server}
                )
                
                for item in response.get('Items', []):
                    player_name = item['PlayerName']
                    history = item.get('RatingHistory', [])
                    
                    # Get today's records
                    la_tz = pytz.timezone("America/Los_Angeles")
                    midnight = la_now.replace(hour=0, minute=0, second=0, microsecond=0)
                    midnight_timestamp = int(midnight.timestamp())
                    
                    # Filter today's records and get the first record before today
                    today_records = []
                    last_record_before_today = None
                    
                    for record in history:
                        timestamp = int(float(record[1]))
                        if timestamp < midnight_timestamp:
                            last_record_before_today = record
                        elif timestamp >= midnight_timestamp:
                            today_records.append(record)
                    
                    if not today_records:
                        continue
                        
                    # Use last record before today as starting point, or first record of today if not available
                    start_mmr = int(last_record_before_today[0]) if last_record_before_today else int(today_records[0][0])
                    end_mmr = int(today_records[-1][0])
                    mmr_change = end_mmr - start_mmr
                    games_played = len(today_records) - (0 if last_record_before_today else 1)  # Don't count first record if it's today's starting point
                    
                    player_data = {
                        'player_name': player_name,
                        'server': server,
                        'start_mmr': start_mmr,
                        'end_mmr': end_mmr,
                        'games_played': games_played
                    }
                    
                    # Add to appropriate lists
                    if mmr_change > 0:
                        climbers.append((mmr_change, player_data))
                    elif mmr_change < 0:
                        unluckiest.append((mmr_change, player_data))
                    if games_played > 0:
                        grinders.append((games_played, player_data))
                        highest_rated.append((end_mmr, player_data))
            
            # Sort and get top N for each category
            top_climbers = sorted(climbers, key=lambda x: x[0], reverse=True)[:top_n]
            top_unluckiest = sorted(unluckiest, key=lambda x: x[0])[:top_n]
            top_grinders = sorted(grinders, key=lambda x: x[0], reverse=True)[:top_n]
            top_rated = sorted(highest_rated, key=lambda x: x[0], reverse=True)[:top_n]

            print(top_climbers)
            
            # Prepare data for Supabase
            supabase_data = []
            for category, data in [
                ('climbers', top_climbers),
                ('unluckiest', top_unluckiest),
                ('grinders', top_grinders),
                ('highest_rated', top_rated)
            ]:
                for rank, (_, player_data) in enumerate(data, 1):  # Add rank starting from 1
                    entry = {
                        'date': today.isoformat(),
                        'category': category,
                        'player_name': player_data['player_name'],
                        'server': player_data['server'],
                        'start_mmr': player_data['start_mmr'],
                        'end_mmr': player_data['end_mmr'],
                        'mmr_change': player_data['end_mmr'] - player_data['start_mmr'],
                        'games_played': player_data['games_played'],
                        'rank': rank  # Add rank to the entry
                    }
                    supabase_data.append(entry)
            
            # Update Supabase using upsert
            if supabase_data:
                self.supabase.table('daily_liiderboards').upsert(supabase_data).execute()
                logger.info(f"Successfully updated daily leaderboards for {today}")
            
        except Exception as e:
            logger.error(f"Error updating daily leaderboards: {e}")
            raise

    async def update_aliases(self):
        """Update aliases from DynamoDB table"""
        self.aliases = self._load_aliases()

    def _load_aliases(self):
        """Load aliases from DynamoDB table"""
        try:
            response = self.alias_table.scan()
            aliases = {
                item["Alias"].lower(): item["PlayerName"].lower()
                for item in response["Items"]
            }
            logger.info(f"Loaded {len(aliases)} aliases")
            return aliases
        except Exception as e:
            logger.error(f"Could not load aliases: {e}")
            return {}

    def _resolve_name(self, player_name, server=None, game_mode="0"):
        """Resolve player name through alias table and check if they exist in database
        
        Args:
            player_name: Name to resolve
            server: Optional server to check (if None, checks all servers)
            game_mode: Game mode to check (defaults to "0" for regular BG)
            
        Returns:
            str: Resolved name if player exists, None otherwise
        """
        if not player_name:
            return None

        # Clean input by removing invisible characters
        lookup_name = "".join(c for c in player_name if c.isprintable()).strip().lower()
        resolved = self.aliases.get(lookup_name, lookup_name)
        if resolved != lookup_name:
            logger.info(f"Resolved alias: {lookup_name} -> {resolved}")
            
        # If the player name is already existing in the database, do not resolve as an alias
        if server:
            # Direct query if server is known
            game_mode_server_player = f"{game_mode}#{server}#{lookup_name.lower()}"
            response = self.table.query(
                KeyConditionExpression="GameModeServerPlayer = :gmsp",
                ExpressionAttributeValues={":gmsp": game_mode_server_player},
            )
            if response.get("Items"):
                return lookup_name
        else:
            # Use PlayerLookupIndex instead of scan
            for check_server in VALID_SERVERS:
                game_mode_server_player = f"{game_mode}#{check_server}#{lookup_name.lower()}"
                response = self.table.query(
                    KeyConditionExpression="GameModeServerPlayer = :gmsp",
                    ExpressionAttributeValues={":gmsp": game_mode_server_player},
                )
                if response.get("Items"):
                    return lookup_name

        return resolved

    def _parse_server(self, server):
        """Normalize server name or return None"""
        if not server:
            return None

        # Strip invisible characters and whitespace
        server = "".join(c for c in server if c.isprintable()).strip()
        if not server:  # If server becomes empty after cleaning
            return None

        parsed = parseServer(server)
        if parsed not in VALID_SERVERS:
            return f"Invalid server: {server}. Valid servers are: NA, EU, AP"
        return parsed

    def _is_valid_server(self, server):
        """Check if server is valid or error message"""
        return isinstance(server, str) and server in VALID_SERVERS

    def get_player_stats(self, player_name, server=None, game_mode="0"):
        """Get a player's current stats"""
        # Resolve alias first
        player_name = self._resolve_name(player_name, server, game_mode)
        if not player_name:
            return None

        if server:
            # Direct query if server is known
            game_mode_server_player = f"{game_mode}#{server}#{player_name.lower()}"
            response = self.table.query(
                KeyConditionExpression="GameModeServerPlayer = :gmsp",
                ExpressionAttributeValues={":gmsp": game_mode_server_player},
            )
        else:
            # Use PlayerLookupIndex instead of scan
            response = self.table.query(
                IndexName="PlayerLookupIndex",
                KeyConditionExpression="PlayerName = :name AND GameMode = :mode",
                ExpressionAttributeValues={
                    ":name": player_name.lower(),
                    ":mode": game_mode,
                },
            )

        if not response.get("Items"):
            return None

        # Return highest rating if multiple servers
        return max(response["Items"], key=lambda x: x["LatestRating"])

    def get_player_history(self, player_name, server=None, game_mode="0", hours=24, start_time=None):
        """Get a player's rating history with the most recent entry before the cutoff."""
        player_name = self._resolve_name(player_name, server, game_mode)
        logger.info(f"Resolved player name: {player_name}")

        if not server:
            stats = self.get_player_stats(player_name, game_mode=game_mode)
            if not stats:
                logger.warning(f"No stats found for {player_name}")
                return None
            server = stats["Server"]
            logger.info(f"Inferred server: {server}")

        game_mode_server_player = f"{game_mode}#{server}#{player_name.lower()}"
        logger.info(f"GameModeServerPlayer: {game_mode_server_player}")

        response = self.table.query(
            KeyConditionExpression="GameModeServerPlayer = :gmsp",
            ExpressionAttributeValues={":gmsp": game_mode_server_player},
        )

        if not response.get("Items"):
            logger.warning(f"No history found for {game_mode_server_player}")
            return None

        # Get full history or filtered by time window
        history = response["Items"][0].get("RatingHistory", [])
        if hours:
            current_time = datetime.now(timezone.utc) if not self.useTestTimestamp else self.testTimestamp
            cutoff = start_time or int((current_time - timedelta(hours=hours)).timestamp())

            la_tz = pytz.timezone("America/Los_Angeles")
            recent_history = []
            last_entry_before_cutoff = None

            for h in history:
                timestamp = int(float(h[1]))
                entry_time_la = datetime.fromtimestamp(timestamp, timezone.utc).astimezone(la_tz)

                if timestamp < cutoff:
                    last_entry_before_cutoff = h
                else:
                    recent_history.append(h)

            if last_entry_before_cutoff:
                recent_history.insert(0, last_entry_before_cutoff)

            return recent_history

        return history

    def get_top_players(self, server, game_mode="0", limit=10):
        """Get top players for a region"""
        game_mode_server = f"{game_mode}#{server}"

        top10Response = self.table.query(
            IndexName="RankLookupIndex",
            KeyConditionExpression=Key("GameModeServer").eq(game_mode_server),
            ProjectionExpression="LatestRating, PlayerName",  # No alias required
            Limit=limit,
            ScanIndexForward=True,  # Ascending order to get top ranks
        )
        top10Response = [
            {"LatestRating": item["LatestRating"], "Server": server, "PlayerName": item["PlayerName"]}
            for item in top10Response.get("Items", [])
        ]

        return top10Response

    def get_rank_player(self, rank, server, game_mode="0"):
        """Get player at specific rank in a region"""
        game_mode_server = f"{game_mode}#{server}"

        response = self.table.query(
            IndexName="RankLookupIndex",
            KeyConditionExpression="GameModeServer = :gms AND CurrentRank = :rank",
            ExpressionAttributeValues={
                ":gms": game_mode_server,
                ":rank": Decimal(str(rank)),
            },
        )

        items = response.get("Items", [])
        return items[0] if items else None

    def get_best_rating(self, player_name, game_mode="0"):
        """Get player's highest rating across all regions"""
        response = self.table.scan(
            FilterExpression="PlayerName = :name AND GameMode = :mode",
            ExpressionAttributeValues={
                ":name": player_name.lower(),
                ":mode": game_mode,
            },
        )

        items = response.get("Items", [])
        return max(items, key=lambda x: x["LatestRating"]) if items else None

    def get_player_peak(self, player_name, server=None, game_mode="0", hours=None):
        """Get player's peak rating within time window. If hours is None, get all-time peak"""
        player_name = self._resolve_name(player_name, server, game_mode)
        # First get current stats to find server if not provided
        if not server:
            stats = self.get_player_stats(player_name, game_mode=game_mode)
            if not stats:
                return None
            server = stats["Server"]

        game_mode_server_player = f"{game_mode}#{server}#{player_name.lower()}"
        response = self.table.query(
            KeyConditionExpression="GameModeServerPlayer = :gmsp",
            ExpressionAttributeValues={":gmsp": game_mode_server_player},
        )

        if not response.get("Items"):
            return None

        # Get full history or filtered by time window
        history = response["Items"][0].get("RatingHistory", [])
        if hours:
            current_time = datetime.now(timezone.utc) if not self.useTestTimestamp else self.testTimestamp
            cutoff = int((current_time - timedelta(hours=hours)).timestamp())
            history = [h for h in history if int(float(h[1])) >= cutoff]

        if not history:
            return None

        peak = max(history, key=lambda x: int(x[0]))
        return {"rating": int(peak[0]), "timestamp": int(float(peak[1]))}

    def get_region_stats(self, server, game_mode="0"):
        """Get region statistics (avg rating, player count, etc)"""
        game_mode_server = f"{game_mode}#{server}"

        countResponse = self.table.scan(
            FilterExpression="GameModeServer = :gms",
            Select="COUNT",
            ExpressionAttributeValues={":gms": game_mode_server},
        )

        top25Response = self.table.query(
            IndexName="RankLookupIndex",
            KeyConditionExpression=Key("GameModeServer").eq(game_mode_server),
            ProjectionExpression="LatestRating",  # No alias required
            Limit=25,
            ScanIndexForward=True,  # Ascending order to get top ranks
        )

        top25Average = sum(item["LatestRating"] for item in top25Response.get("Items", [])) // 25
        count = countResponse.get("Count", 0)

        return {'count': count, 'top25Average': top25Average}

    def _normalize_stats(self, stats):
        """Normalize stats dictionary to use consistent key names
        Converts:
            - current_rank -> CurrentRank
            - current_rating -> LatestRating
            - server -> Server
        """
        if not stats:
            return stats

        normalized = stats.copy()
        key_mapping = {
            "current_rank": "CurrentRank",
            "current_rating": "LatestRating",
            "server": "Server",
        }

        for old_key, new_key in key_mapping.items():
            if old_key in normalized:
                normalized[new_key] = normalized.pop(old_key)

        return normalized

    def _format_no_games_response(self, player_name, stats, timeframe=""):
        """Format consistent response for when a player has no games played"""
        # Use the actual player name from stats if available (for rank lookups)
        if not stats:
            stats = self.get_player_stats(player_name)

        display_name = stats.get("PlayerName", player_name)
        return (
            f"{display_name} is rank {stats['CurrentRank']} in {stats['Server']} "
            f"at {stats['LatestRating']} with no games played{timeframe}"
        )

    def format_yesterday_stats(self, player_or_rank, server=None, game_mode="0"):
        player_name, server, error = self._handle_rank_or_name(player_or_rank, server, game_mode)
        if error:
            return error

        resolved_name = self._resolve_name(player_name, server, game_mode)

        if not resolved_name:
            return f"{resolved_name} is not on any{' duo' if game_mode == '1' else ''} BG leaderboards."

        # Infer the server if not provided
        if not server:
            server = self.get_most_recent_server(resolved_name, game_mode)
            if not server:
                return f"{resolved_name} is not on any{' duo' if game_mode == '1' else ''} BG leaderboards."

        # Calculate time range for yesterday
        midnight_timestamp = self.get_la_midnight_today()
        starting_timestamp = midnight_timestamp - (24 * 60 * 60)  # Start of yesterday
        ending_timestamp = midnight_timestamp - 1  # End of yesterday

        return self._format_stats_in_range(
            resolved_name, server, game_mode, starting_timestamp, ending_timestamp
        )

    def _format_stats_in_range(self, player_or_rank, server, game_mode, start_timestamp, end_timestamp):
        """
        Fetch and format stats for a player in the given time range.
        """
        player_name, server, error = self._handle_rank_or_name(player_or_rank, server, game_mode)
        if error:
            return error

        history = self.get_player_history(player_name, server, game_mode, hours=24, start_time=start_timestamp)
        stats = self.get_player_stats(player_name, server, game_mode)

        if not stats:
            return f"{player_name} is not on {server if server else 'any'}{' duo' if game_mode == '1' else ''} BG leaderboards."

        if not history:
            return self._format_no_games_response(player_name, stats)

        # Sort history by timestamp (if not already sorted)
        history = sorted(history, key=lambda x: int(float(x[1])))

        # Initialize variables
        last_entry_before_range = None
        filtered_history = []  # Properly initialize the list

        # Determine the last entry before the range and filter the history
        for entry in history:
            timestamp = int(float(entry[1]))
            if timestamp < start_timestamp:
                last_entry_before_range = entry  # Keep track of the last entry before the range
            elif start_timestamp <= timestamp <= end_timestamp:
                filtered_history.append(entry)

        if not filtered_history or len(filtered_history) < 2:
            return self._format_no_games_response(player_name, None)

        # Determine starting_rating
        starting_rating = int(last_entry_before_range[0]) if last_entry_before_range else int(filtered_history[0][0])
        starting_timestamp = int(float(last_entry_before_range[1])) if last_entry_before_range else int(float(filtered_history[0][1]))

        # Calculate deltas
        deltas = []
        for i, entry in enumerate(filtered_history):
            rating = int(entry[0])
            if i == 0:
                # First delta uses starting_rating if set, else compares with the same value
                delta = rating - (starting_rating if starting_rating is not None else rating)
            else:
                delta = rating - int(filtered_history[i - 1][0])

            if delta != 0:
                deltas.append(delta)

        # Calculate total change
        total_change = int(filtered_history[-1][0]) - starting_rating

        # Format response
        # If starting_timestamp is from today, count it in games_played
        if starting_timestamp >= start_timestamp:
            games_played = len(filtered_history) - 1
        else:
            games_played = len(filtered_history)
        changes_str = ", ".join(f"{'+' if delta > 0 else ''}{delta}" for delta in deltas)
        progression = f"{'climbed' if total_change > 0 else 'fell'} from {starting_rating} to {filtered_history[-1][0]} ({total_change:+})"
        if not server:
            # Use the server from the player's stats if available
            stats = self.get_player_stats(player_name, game_mode=game_mode)
            server = stats["Server"] if stats else "Unknown"
        else:
            server = server.upper()

        # Check for duplicate names
        dup_count = self.get_duplicate_names_count(player_name, game_mode)
        dup_msg = self._format_duplicate_names_message(player_name, dup_count, game_mode)

        return (
            f"{player_name} {progression} in {server} over {games_played} game{'s' if games_played > 1 else ''}: {changes_str}{dup_msg}"
        )

    def get_starting_rating(self, player_history, start_timestamp):
        """
        Determine the starting rating for a given time range.
        - Uses the last entry before the range if available.
        - Otherwise, defaults to the first entry in the range.
        - Handles duplicate ratings at period boundaries to avoid redundant entries.

        Args:
            player_history: List of history entries (rating, timestamp).
            start_timestamp: Start of the time range.

        Returns:
            starting_rating, adjusted_history: The determined starting rating and the filtered history.
        """
        last_entry_before_range = None
        filtered_history = []
        current_rating = None

        # Sort history by timestamp to ensure proper ordering
        sorted_history = sorted(player_history, key=lambda x: int(float(x[1])))

        for entry in sorted_history:
            rating, timestamp = int(entry[0]), int(float(entry[1]))
            
            if timestamp < start_timestamp:
                last_entry_before_range = entry
                current_rating = rating
            elif timestamp >= start_timestamp:
                # Only add entry if it represents a rating change
                if current_rating is None or rating != current_rating:
                    filtered_history.append(entry)
                    current_rating = rating

        # Determine starting rating
        if last_entry_before_range:
            starting_rating = int(last_entry_before_range[0])
        elif filtered_history:
            starting_rating = int(filtered_history[0][0])
        else:
            return None, []

        return starting_rating, filtered_history

    def format_daily_stats(self, player_or_rank, server=None, game_mode="0"):
        player_name, server, error = self._handle_rank_or_name(player_or_rank, server, game_mode)
        if error:
            return error

        resolved_name = self._resolve_name(player_name, server, game_mode)

        if not resolved_name:
            return f"{resolved_name} is not on any{' duo' if game_mode == '1' else ''} BG leaderboards."

        # Infer the server if not provided
        if not server:
            server = self.get_most_recent_server(resolved_name, game_mode)
            if not server:
                return f"{resolved_name} is not on any{' duo' if game_mode == '1' else ''} BG leaderboards."

        # Calculate time range
        midnight_timestamp = self.get_la_midnight_today()
        now_timestamp = int(datetime.now().timestamp()) if not self.useTestTimestamp else int(self.testTimestamp.now().timestamp())

        return self._format_stats_in_range(
            resolved_name, server, game_mode, midnight_timestamp, now_timestamp
        )

    def get_most_recent_server(self, player_name, game_mode="0"):
        """
        Infer the most recent server where the player has activity.
        """
        recent_activity = {}
        for region in VALID_SERVERS:
            history = self.get_player_history(player_name, region, game_mode)
            if history:
                recent_activity[region] = int(float(history[-1][1]))  # Use the last timestamp

        if recent_activity:
            return max(recent_activity, key=recent_activity.get)  # Server with the most recent activity
        return None  # No activity found

    def format_peak_stats(self, player_or_rank, server=None, game_mode="0"):
        """
        Format peak stats for a player in chat-ready format.
        """
        # Resolve rank or name and determine server
        player_name, server, error = self._handle_rank_or_name(player_or_rank, server, game_mode)
        if error:
            return error

        # Resolve alias for player name
        resolved_name = self._resolve_name(player_name, server, game_mode)
        if not resolved_name:
            return f"{player_or_rank} could not be resolved to a valid player."

        # If no server provided, find the server with the highest peak
        if not server:
            stats = self.get_player_stats(resolved_name, game_mode=game_mode)
            if not stats:
                return f"{resolved_name} is not on any{' duo' if game_mode == '1' else ''} BG leaderboards."
            server = stats.get("Server", "Unknown")

        # Fetch the peak stats for the resolved player and server
        peak = self.get_player_peak(resolved_name, server, game_mode)
        if not peak:
            return f"{resolved_name} has no rating history in {server}."

        # Convert timestamp to integer for datetime.fromtimestamp
        peak_timestamp = int(peak['timestamp'])

        # Format and return the peak stats
        return (
            f"{resolved_name}'s peak rating in {server} this season: {peak['rating']} "
            f"on {self.format_la_time(peak_timestamp)}"
        )

    def get_duplicate_names_count(self, base_name, game_mode="0"):
        """
        Check for duplicate names (e.g., mia2, mia3, etc.) and return the count of duplicates.
        Returns 0 if no duplicates exist.
        """
        count = 1  # Start at 1 since we're checking for mia2, mia3, etc.
        while True:
            # Check if the next numbered name exists
            next_name = f"{base_name}{count + 1}"
            response = self.table.query(
                IndexName="PlayerLookupIndex",
                KeyConditionExpression="PlayerName = :name AND GameMode = :mode",
                ExpressionAttributeValues={
                    ":name": next_name.lower(),
                    ":mode": game_mode,
                },
            )
            
            if not response.get("Items"):
                # No more duplicates found
                break
            count += 1
            
        return count if count > 1 else 0

    def _format_duplicate_names_message(self, base_name, count, game_mode="0"):
        # Temp remove this message while I figure out how to handle fake duplicates
        return ""
        """Format a message about duplicate names if they exist"""
        if count == 0:
            return ""
            
        duplicates = [f"{base_name}{i}" for i in range(2, count + 1)]
        if game_mode == "1":
            duplicates = [f"{name} (duo)" for name in duplicates]
            
        return f" (Note: {', '.join(duplicates)} also exist{'s' if len(duplicates) == 1 else ''})"

    def format_player_stats(self, player_or_rank, server=None, game_mode="0"):
        """Format player stats in chat-ready format"""
        if server:
            server = self._parse_server(server)
            if not self._is_valid_server(server):
                return server  # Return error message

        player_name, server, error = self._handle_rank_or_name(
            player_or_rank, server, game_mode
        )
        if error:
            return error

        # Resolve alias before lookup
        resolved_name = self._resolve_name(player_name, server, game_mode)

        if server:
            # Direct server lookup
            stats = self.get_player_stats(resolved_name, server, game_mode)
            if not stats:
                return f"{resolved_name} is not on {server if server else 'any'}{' duo' if game_mode == '1' else ''} BG leaderboards"
                
            # Check for duplicate names
            dup_count = self.get_duplicate_names_count(resolved_name, game_mode)
            dup_msg = self._format_duplicate_names_message(resolved_name, dup_count, game_mode)
            
            return f"{resolved_name} is rank {stats['CurrentRank']} in {stats['Server']} at {stats['LatestRating']}{dup_msg}"

        # Find best rating across servers
        response = self.table.query(
            IndexName="PlayerLookupIndex",
            KeyConditionExpression="PlayerName = :name AND GameMode = :mode",
            ExpressionAttributeValues={
                ":name": resolved_name.lower(),
                ":mode": game_mode,
            })

        items = response.get("Items", [])
        if not items:
            return f"{resolved_name} is not on {server if server else 'any'}{' duo' if game_mode == '1' else ''} BG leaderboards"

        # Get best rating and other servers
        best = min(items, key=lambda x: x["CurrentRank"])
        others = [i for i in items if i["Server"] != best["Server"]]

        # Check for duplicate names
        dup_count = self.get_duplicate_names_count(resolved_name, game_mode)
        dup_msg = self._format_duplicate_names_message(resolved_name, dup_count, game_mode)

        if others:
            other = max(others, key=lambda x: x["CurrentRank"])
            return (
                f"{resolved_name} is rank {best['CurrentRank']} in {best['Server']} at {best['LatestRating']} "
                f"(also rank {other['CurrentRank']} {other['Server']} at {other['LatestRating']}) {dup_msg}"
            )

        return f"{resolved_name} is rank {best['CurrentRank']} in {best['Server']} at {best['LatestRating']} {dup_msg}"

    def format_region_stats(self, server, game_mode="0"):
        """Format region stats in chat-ready format"""
        server = self._parse_server(server)
        if not self._is_valid_server(server):
            return server  # Return error message

        stats = self.get_region_stats(server, game_mode)
        if not stats:
            return f"No stats available for {server}"

        return f"{server} has {stats['count']} {'player' if stats['count'] == 1 else 'players'} and Top 25 avg is {stats['top25Average']}"

    def format_top_players(self, server, game_mode="0"):
        """Format top 10 players in chat-ready format"""
        if not server:
            return self.format_top_players_global(game_mode)

        server = self._parse_server(server)
        if not self._is_valid_server(server):
            return server  # Return error message

        players = self.get_top_players(server, game_mode)
        if not players:
            return f"No players found in {server}"

        formatted = [
            f"{i+1}. {p['PlayerName']}: {p['LatestRating']}"
            for i, p in enumerate(players)
        ]

        return f"Top 10 {server}: {', '.join(formatted)}"

    def _handle_rank_or_name(self, player_or_rank, server=None, game_mode="0"):
        """Handle rank or player name lookup"""
        # Clean server first to handle invisible characters
        server = self._parse_server(server)

        # Handle rank lookup
        try:
            rank = int(player_or_rank)
            if not server:
                return None, None, "Server is required for rank lookup"

            if not self._is_valid_server(server):
                return None, None, server  # Return error message from _parse_server

            player = self.get_rank_player(rank, server, game_mode)
            if not player:
                return None, None, f"No player found at rank {rank} in {server}{' duo' if game_mode == '1' else ''} BG"

            return player["PlayerName"], server, None

        # Handle player name lookup
        except ValueError:
            player_name = player_or_rank
            if server and not self._is_valid_server(server):
                return None, None, server
            return player_name, server, None

    def format_weekly_stats(self, player_or_rank, server=None, game_mode="0"):
        """
        Format weekly stats for a player in chat-ready format.
        """
        if server:
            server = self._parse_server(server)
            if not self._is_valid_server(server):
                return server  # Return error message

        player_name, server, error = self._handle_rank_or_name(player_or_rank, server, game_mode)
        if error:
            return error

        resolved_name = self._resolve_name(player_name, server, game_mode)
        stats = self.get_player_stats(resolved_name, server, game_mode)

        if not resolved_name or not stats:
            return f"{resolved_name} is not on {'any' if not server else server} BG{' duo' if game_mode == '1' else ''} leaderboards"

        # Infer the server if not provided
        if not server:
            server = self.get_most_recent_server(player_name, game_mode)
            if not server:
                return f"{resolved_name} is not on {'any' if not server else server} BG{' duo' if game_mode == '1' else ''} leaderboards"

        monday_midnight_timestamp = self.get_la_monday_midnight()

        # Fetch entire weekly history
        history = self.get_player_history(
            resolved_name, server, game_mode, start_time=monday_midnight_timestamp - (24 * 60 * 60)
        )

        logger.info(f"Weekly stats for {resolved_name} in {server}:")
        logger.info(f"Monday midnight timestamp: {monday_midnight_timestamp}")
        logger.info(f"History entries count: {len(history) if history else 0}")

        # Initialize variables
        starting_rating = None
        daily_deltas = [0] * 7
        daily_entries = [[] for _ in range(7)]
        la_tz = pytz.timezone("America/Los_Angeles")
        monday_midnight = datetime.fromtimestamp(monday_midnight_timestamp, la_tz)

        logger.info("Calculating daily starting ratings...")
        for i in range(7):
            day_start = monday_midnight_timestamp + (i * 24 * 60 * 60)
            start_rating = self.get_starting_rating(history, day_start)[0]
            daily_entries[i].append(start_rating)
            logger.info(f"Day {i} starting rating: {start_rating}")

        # Determine starting rating and daily entries
        last_valid_rating = None
        logger.info("Processing history entries...")
        for entry in history:
            rating, timestamp = int(entry[0]), int(float(entry[1]))
            entry_time = datetime.fromtimestamp(timestamp, timezone.utc).astimezone(la_tz)
            days_since_monday = (entry_time - monday_midnight).days
            
            logger.info(f"Entry: rating={rating}, timestamp={timestamp}, days_since_monday={days_since_monday}")

            if days_since_monday < 0:
                last_valid_rating = rating
                logger.info(f"Found pre-Monday rating: {rating}")
            elif 0 <= days_since_monday < 7:
                daily_entries[days_since_monday].append(rating)
                logger.info(f"Added rating {rating} to day {days_since_monday}")

        # Set the starting rating
        starting_rating = last_valid_rating if last_valid_rating is not None else int(history[0][0])
        logger.info(f"Final starting rating: {starting_rating}")

        # Remove adjacent duplicate ratings from each day's entries
        for day in range(len(daily_entries)):
            if daily_entries[day]:
                filtered_entries = [daily_entries[day][0]]  # Keep the first entry
                for entry in daily_entries[day][1:]:
                    if entry != filtered_entries[-1]:  # Compare ratings
                        filtered_entries.append(entry)
                daily_entries[day] = filtered_entries

        # Calculate daily deltas with proper carry-over for starting ratings
        logger.info("Calculating daily deltas...")
        for day, entries in enumerate(daily_entries):
            previous_day_last_rating = (
                starting_rating if day == 0 else (daily_entries[day - 1][-1] if daily_entries[day - 1] else starting_rating)
            )
            
            if entries:
                daily_deltas[day] = entries[-1] - previous_day_last_rating
                logger.info(f"Day {day}: prev_rating={previous_day_last_rating}, last_rating={entries[-1]}, delta={daily_deltas[day]}")
            else:
                daily_deltas[day] = 0
                logger.info(f"Day {day}: No games played")

        # Calculate total games played and total change
        games_played = sum(len(entries[1:]) for entries in daily_entries)  # Skip the starting rating for each day
        total_change = sum(daily_deltas)

        if games_played == 0:
            return self._format_no_games_response(player_name, stats, " this week")

        # Determine the current rating at the end of the week
        current_rating = daily_entries[-1][-1] if daily_entries[-1] else starting_rating + total_change

        # Format daily deltas as a string
        day_names = ["M", "T", "W", "Th", "F", "Sa", "Su"]
        changes_str = ", ".join(f"{day}: {'+' if delta > 0 else ''}{delta}" for day, delta in zip(day_names, daily_deltas))

        # Determine climb or fall wording and emote
        action = "climbed" if total_change > 0 else "fell"
        emote = "liiHappyCat" if total_change > 0 else "liiCat"

        # Build the response
        return (
            f"{resolved_name} {action} from {starting_rating} to {current_rating} "
            f"({'+' if total_change > 0 else ''}{total_change}) in {server} "
            f"over {games_played} game{'s' if games_played > 1 else ''}: {changes_str} {emote}"
        )

    def format_last_week_stats(self, player_or_rank, server=None, game_mode="0"):
        """
        Format stats for the previous week for a player in chat-ready format.
        """
        if server:
            server = self._parse_server(server)
            if not self._is_valid_server(server):
                return server  # Return error message

        player_name, server, error = self._handle_rank_or_name(player_or_rank, server, game_mode)
        if error:
            return error

        resolved_name = self._resolve_name(player_name, server, game_mode)
        stats = self.get_player_stats(resolved_name, server, game_mode)

        if not resolved_name or stats is None:
            return f"{resolved_name} is not on {'any' if not server else server} BG{' duo' if game_mode == '1' else ''} leaderboards"

        # Infer the server if not provided
        if not server:
            server = self.get_most_recent_server(player_name, game_mode)
            if not server:
                return f"{resolved_name} is not on {'any' if not server else server} BG{' duo' if game_mode == '1' else ''} leaderboards"

        # Get timestamps for last week's Monday and this week's Monday
        this_monday_midnight = self.get_la_monday_midnight()
        last_monday_midnight = this_monday_midnight - (7 * 24 * 60 * 60)  # 7 days before

        # Fetch history starting from Sunday before last week (to get starting rating)
        history = self.get_player_history(
            resolved_name, server, game_mode, start_time=last_monday_midnight - (24 * 60 * 60)
        )

        # Initialize variables
        daily_deltas = [0] * 7
        daily_entries = [[] for _ in range(7)]
        la_tz = pytz.timezone("America/Los_Angeles")
        last_monday = datetime.fromtimestamp(last_monday_midnight, la_tz)

        logger.info("Calculating daily starting ratings for last week...")
        for i in range(7):
            day_start = last_monday_midnight + (i * 24 * 60 * 60)
            start_rating = self.get_starting_rating(history, day_start)[0]
            daily_entries[i].append(start_rating)
            logger.info(f"Last week Day {i} starting rating: {start_rating}")

        # Determine starting rating and daily entries
        last_valid_rating = None
        logger.info("Processing last week's history entries...")
        for entry in history:
            rating, timestamp = int(entry[0]), int(float(entry[1]))
            entry_time = datetime.fromtimestamp(timestamp, timezone.utc).astimezone(la_tz)
            days_since_monday = (entry_time - last_monday).days
            
            logger.info(f"Entry: rating={rating}, timestamp={timestamp}, days_since_monday={days_since_monday}")

            if days_since_monday < 0:
                last_valid_rating = rating
                logger.info(f"Found pre-Monday rating: {rating}")
            elif 0 <= days_since_monday < 7:
                daily_entries[days_since_monday].append(rating)
                logger.info(f"Added rating {rating} to day {days_since_monday}")

        # Set the starting rating
        starting_rating = last_valid_rating if last_valid_rating is not None else int(history[0][0])
        logger.info(f"Final starting rating for last week: {starting_rating}")

        # Remove adjacent duplicate ratings from each day's entries
        for day in range(len(daily_entries)):
            if daily_entries[day]:
                filtered_entries = [daily_entries[day][0]]  # Keep the first entry
                for entry in daily_entries[day][1:]:
                    if entry != filtered_entries[-1]:  # Compare ratings
                        filtered_entries.append(entry)
                daily_entries[day] = filtered_entries

        # Calculate daily deltas with proper carry-over for starting ratings
        logger.info("Calculating last week's daily deltas...")
        for day, entries in enumerate(daily_entries):
            previous_day_last_rating = (
                starting_rating if day == 0 else (daily_entries[day - 1][-1] if daily_entries[day - 1] else starting_rating)
            )
            
            if entries:
                daily_deltas[day] = entries[-1] - previous_day_last_rating
                logger.info(f"Day {day}: prev_rating={previous_day_last_rating}, last_rating={entries[-1]}, delta={daily_deltas[day]}")
            else:
                daily_deltas[day] = 0
                logger.info(f"Day {day}: No games played")

        # Calculate total games played and total change
        games_played = sum(len(entries[1:]) for entries in daily_entries)  # Skip the starting rating for each day
        total_change = sum(daily_deltas)

        # If no games were played, return the no games response
        if games_played == 0:
            return self._format_no_games_response(resolved_name, stats, " last week")

        # Determine the final rating at the end of last week
        final_rating = daily_entries[-1][-1] if daily_entries[-1] else starting_rating + total_change

        # Format daily deltas as a string
        day_names = ["M", "T", "W", "Th", "F", "Sa", "Su"]
        changes_str = ", ".join(f"{day}: {'+' if delta > 0 else ''}{delta}" for day, delta in zip(day_names, daily_deltas))

        # Determine climb or fall wording and emote
        action = "climbed" if total_change > 0 else "fell"
        emote = "liiHappyCat" if total_change > 0 else "liiCat"

        # Build the response
        return (
            f"{resolved_name} {action} from {starting_rating} to {final_rating} "
            f"({'+' if total_change > 0 else ''}{total_change}) in {server} "
            f"over {games_played} game{'s' if games_played > 1 else ''} last week: {changes_str} {emote}"
        )

    def format_milestone_stats(self, rating_threshold, server=None, game_mode="0"):
        """Format milestone stats for chat"""
        if server:
            server = self._parse_server(server)
            if not self._is_valid_server(server):
                return server  # Return error message

        # Get both regular and duo milestones
        regular = self._get_milestone(rating_threshold, server, "0")
        duo = self._get_milestone(rating_threshold, server, "1")

        # Format responses
        k_rating = rating_threshold // 1000

        if not regular and not duo:
            if server:
                return f"No one has reached {k_rating}k in {server} yet!"
            return f"No one has reached {k_rating}k in any server yet!"

        # Build combined response
        response = []

        # Add regular milestone if exists
        if regular:
            # Convert UTC to NY time
            ny_tz = pytz.timezone("America/New_York")
            utc_time = datetime.fromtimestamp(
                int(float(regular["Timestamp"])), pytz.UTC
            )
            ny_time = utc_time.astimezone(ny_tz)
            date = ny_time.strftime(
                "%B %d %I:%M %p ET"
            )  # e.g., "December 03 3:45 PM ET"

            server_str = (
                server if server else regular["SeasonGameModeServer"].split("-")[2]
            )
            response.append(
                f"{regular['PlayerName']} was the first to reach {k_rating}k in {server_str} on {date}"
            )

        # Add duo milestone if exists
        if duo:
            ny_tz = pytz.timezone("America/New_York")
            utc_time = datetime.fromtimestamp(
                int(float(duo["Timestamp"])), pytz.UTC
            )
            ny_time = utc_time.astimezone(ny_tz)
            date = ny_time.strftime("%B %d %I:%M %p ET")

            server_str = (
                server if server else duo["SeasonGameModeServer"].split("-")[2]
            )
            response.append(
                f"In Duos: {duo['PlayerName']} was the first to reach {k_rating}k in {server_str} on {date}"
            )

        return " | ".join(response)

    def _get_milestone(self, rating_threshold, server=None, game_mode="0"):
        """Helper to get milestone data for a specific mode"""
        try:
            milestone_table = boto3.resource("dynamodb").Table("MilestoneTracking")
            season = "14"

            if server:
                server = parseServer(server)
                if not server:
                    return None

                season_game_mode_server = f"{season}-{game_mode}-{server}"
                response = milestone_table.query(
                    KeyConditionExpression="SeasonGameModeServer = :sgs AND Milestone = :m",
                    ExpressionAttributeValues={
                        ":sgs": season_game_mode_server,
                        ":m": Decimal(str(rating_threshold)),
                    },
                )
            else:
                response = milestone_table.scan(
                    FilterExpression="Milestone = :m AND begins_with(SeasonGameModeServer, :prefix)",
                    ExpressionAttributeValues={
                        ":m": Decimal(str(rating_threshold)),
                        ":prefix": f"{season}-{game_mode}-",
                    },
                )

            items = response.get("Items", [])
            return min(items, key=lambda x: int(x["Timestamp"])) if items else None

        except Exception as e:
            logger.error(f"Error in _get_milestone: {str(e)}")
            return None

    def get_top_players_global(self, game_mode="0", limit=10):
        """Get top players globally across all servers"""
        try:
            top10Global = []

            for region in ['NA', 'EU', 'AP']:
                game_mode_server = f"{game_mode}#{region}"
                top10Response = self.table.query(
                    IndexName="RankLookupIndex",
                    KeyConditionExpression=Key("GameModeServer").eq(game_mode_server),
                    ProjectionExpression="LatestRating, PlayerName",  # No alias required
                    Limit=limit,
                    ScanIndexForward=True,  # Ascending order to get top ranks
                )
                top10Response = [
                    {"LatestRating": item["LatestRating"], "Server": region, "PlayerName": item["PlayerName"]}
                    for item in top10Response.get("Items", [])
                ]

                top10Global.extend(top10Response)

            top10Global = sorted(top10Global, key=lambda x: int(x["LatestRating"]), reverse=True)[:limit]

            return top10Global

        except Exception as e:
            logger.error(f"Error getting top players globally: {str(e)}")
            return []

    def format_top_players_global(self, game_mode="0"):
        """Format global top 10 players in chat-ready format"""
        players = self.get_top_players_global(game_mode)
        if not players:
            return "No players found globally"

        # Format each player as "name (rating) from server"
        formatted = [
            f"{i+1}. {p['PlayerName']}: {p['LatestRating']} ({p['Server']})"
            for i, p in enumerate(players)
        ]

        return f"Top 10 globally: {', '.join(formatted)}"

    def add_alias(self, alias, player_name):
        """Add an alias for a player"""
        try:
            self.alias_table.put_item(
                Item={"Alias": alias, "PlayerName": player_name}
            )
            return f"Alias {alias} added for {player_name}"
        except Exception as e:
            logger.error(f"Error adding alias: {str(e)}")
            return f"Error adding alias: {str(e)}"

    def delete_alias(self, alias):
        """Delete an alias"""
        try:
            self.alias_table.delete_item(Key={"Alias": alias})
            return f"Alias {alias} deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting alias: {str(e)}")
            return f"Error deleting alias: {str(e)}"

    def add_channel(self, channel, player_name=channel):
        """Add a channel to the channel table"""
        try:
            self.channel_table.put_item(Item={"ChannelName": channel, "PlayerName": player_name})
            return f"Channel {channel} added successfully with the player_name:{player_name}"
        except Exception as e:
            logger.error(f"Error adding channel: {str(e)}")
            return f"Error adding channel: {str(e)}"

    def delete_channel(self, channel):
        """Delete a channel from the channel table"""
        try:
            self.channel_table.delete_item(Key={"ChannelName": channel})
            return f"Channel {channel} deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting channel: {str(e)}")
            return f"Error deleting channel: {str(e)}"

    def get_patch_link(self):
        try:
            return self.patch_link
        except Exception as e:
            logger.error(f"Error getting patch link: {str(e)}")
            return f"Error getting patch link: {str(e)}"

    async def fetchPatchLink(self):
        # URL of the API
        api_url = "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=4"

        # Send a request to fetch the JSON data from the API
        response = requests.get(api_url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()

            # Loop through each article in the data
            for article in data:
                content = article.get("content", "")  # Extract the content field
                # Check if 'battlegrounds' is mentioned in the content
                if "battlegrounds" in content.lower():
                    # Extract and print the article's 'defaultUrl'
                    article_url = article.get("defaultUrl")
                    title = article.get("title")
                    self.patch_link = f"{title}: {article_url}"
                    return
            else:
                logger.error("Patch link not found")
        else:
            logger.error(f"Failed to retrieve data. Status code: {response.status_code}")

    def get_la_midnight_today(self):
        """Get UTC timestamp for LA midnight today"""
        la_tz = pytz.timezone("America/Los_Angeles")
        utc_now = datetime.fromtimestamp(time.time(), pytz.UTC) if not self.useTestTimestamp else datetime.fromtimestamp(self.testTimestamp.timestamp(), pytz.UTC)
        la_now = utc_now.astimezone(la_tz)
        la_midnight = la_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(la_midnight.astimezone(pytz.UTC).timestamp())

    def get_la_monday_midnight(self):
        """Get UTC timestamp for LA midnight of current week's Monday"""
        la_tz = pytz.timezone("America/Los_Angeles")
        utc_now = datetime.fromtimestamp(time.time(), pytz.UTC) if not self.useTestTimestamp else datetime.fromtimestamp(self.testTimestamp.timestamp(), pytz.UTC)
        la_now = utc_now.astimezone(la_tz)
        days_since_monday = la_now.weekday()  # Monday = 0, Sunday = 6
        la_monday = la_now - timedelta(days=days_since_monday)
        la_monday_midnight = la_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(la_monday_midnight.astimezone(pytz.UTC).timestamp())

    def format_la_time(self, timestamp):
        """Format UTC timestamp to LA time string"""
        la_tz = pytz.timezone("America/Los_Angeles")
        utc_time = datetime.fromtimestamp(timestamp, pytz.UTC)
        la_time = utc_time.astimezone(la_tz)
        return la_time.strftime("%b %d, %Y")