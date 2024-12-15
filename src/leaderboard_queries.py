import os
import aiocron
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
import requests
from discord import channel
import pytz

from logger import setup_logger
from parseRegion import parseServer

logger = setup_logger("leaderboard_queries")

VALID_SERVERS = {"NA", "EU", "AP"}


class LeaderboardDB:
    def __init__(self, test_db=None, table_name="HearthstoneLeaderboard"):
        """Initialize DB connection"""
        if test_db:
            self.dynamodb = test_db
            self.table = test_db
            self.alias_table = test_db  # For testing
            logger.info("Using test DB for all tables")
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

        # Load aliases
        self.aliases = self._load_aliases()
        self.patch_link = "Currently fetching patch link..."
        logger.info(f"Initialized with {len(self.aliases)} aliases")
        
        # Set up cron job to update aliases every minute
        self.cron = aiocron.crontab("*/1 * * * *", func=self.update_aliases)
        self.fetch_patch_link_cron = aiocron.crontab('* * * * *', func=self.fetchPatchLink)

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

    def _resolve_name(self, player_name):
        """Resolve player name through alias table"""
        if not player_name:
            return None

        # Clean input by removing invisible characters
        lookup_name = "".join(c for c in player_name if c.isprintable()).strip().lower()
        resolved = self.aliases.get(lookup_name, lookup_name)
        if resolved != lookup_name:
            logger.info(f"Resolved alias: {lookup_name} -> {resolved}")
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
        player_name = self._resolve_name(player_name)
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

    def get_player_history(self, player_name, server=None, game_mode="0", hours=24):
        """Get a player's rating history"""
        player_name = self._resolve_name(player_name)
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

        # Get history within time window using UTC
        cutoff = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        history = response["Items"][0].get("RatingHistory", [])
        recent_history = [h for h in history if h[1] >= cutoff]

        return recent_history

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
        player_name = self._resolve_name(player_name)
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
            cutoff = int(
                (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
            )
            history = [h for h in history if h[1] >= cutoff]

        if not history:
            return None

        peak = max(history, key=lambda x: x[0])
        return {"rating": peak[0], "timestamp": peak[1]}

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

    def get_daily_stats(self, player_name, server=None, game_mode="0"):
        """Get a player's daily stats including games played and MMR changes"""
        server = self._parse_server(server)
        if server and not self._is_valid_server(server):
            return server  # Return error message

        # Handle rank lookup first
        try:
            rank = int(player_name)
            if server:
                player = self.get_rank_player(rank, server, game_mode)
                if player:
                    player_name = player["PlayerName"]
        except ValueError:
            # Not a rank lookup, resolve alias
            player_name = self._resolve_name(player_name)

        history = self.get_player_history(player_name, server, game_mode, hours=24)
        if not history:
            # Try to get current stats to distinguish between "not found" and "no games"
            stats = self.get_player_stats(player_name, server, game_mode)
            if not stats:
                return {"found": False}

            return {
                "found": True,
                "has_games": False,
                "CurrentRank": stats.get("CurrentRank", 0),
                "LatestRating": stats.get("LatestRating", 0),
                "Server": stats.get("Server", server or "Unknown"),
                "PlayerName": player_name,
            }

        # A player has games only if they have 2 or more entries
        has_games = len(history) >= 2

        # Get current stats for rank info
        stats = self.get_player_stats(player_name, server, game_mode)
        if not stats:
            stats = {
                "CurrentRank": 0,
                "LatestRating": 0,
                "Server": server or "Unknown",
                "PlayerName": player_name,
            }

        # Calculate changes only if they have games
        changes = []
        if has_games:
            for i in range(1, len(history)):
                change = int(history[i][0]) - int(history[i - 1][0])
                changes.append(change)

        return {
            "found": True,
            "has_games": has_games,
            "CurrentRank": stats.get("CurrentRank", 0),
            "LatestRating": stats.get("LatestRating", 0),
            "Server": stats.get("Server", server or "Unknown"),
            "PlayerName": player_name,
            "start_rating": int(history[0][0]),
            "current_rating": int(history[-1][0]),
            "games_played": len(changes),
            "rating_changes": changes,
        }

    def _format_no_games_response(self, player_name, stats, timeframe=""):
        """Format consistent response for when a player has no games played"""
        # Use the actual player name from stats if available (for rank lookups)
        display_name = stats.get("PlayerName", player_name)
        return (
            f"{display_name} is rank {stats['CurrentRank']} in {stats['Server']} "
            f"at {stats['LatestRating']} with 0 games played{timeframe}"
        )

    def format_daily_stats(self, player_or_rank, server=None, game_mode="0"):
        """Format daily stats for a player in chat-ready format"""
        # Clean input first
        player_or_rank = "".join(c for c in player_or_rank if c.isprintable()).strip()

        player_name, server, error = self._handle_rank_or_name(
            player_or_rank, server, game_mode
        )
        if error:
            return error

        resolved_name = self._resolve_name(
            player_name
        )  # <-- Here's the alias resolution

        stats = self.get_daily_stats(resolved_name, server, game_mode)

        if not stats["found"]:
            return f"{resolved_name} is not on {server if server else 'any'} BG leaderboards"

        if not stats["has_games"]:
            # Use PlayerName from stats for rank lookups
            display_name = stats.get("PlayerName", resolved_name)
            return self._format_no_games_response(display_name, stats)

        # Calculate total MMR change
        total_change = stats["current_rating"] - stats["start_rating"]
        total_change_str = f" ({'+' if total_change > 0 else ''}{total_change})"

        # Use resolved name from stats
        display_name = stats.get("PlayerName", resolved_name)

        changes_str = ", ".join(
            f"{'+' if c > 0 else ''}{c}" for c in stats["rating_changes"]
        )
        return (
            f"{display_name} {'climbed' if total_change > 0 else 'fell'} from {stats['start_rating']} to "
            f"{stats['current_rating']} ({'+' if total_change > 0 else '-'}{abs(total_change)}) in {stats['Server']} "
            f"over {stats['games_played']} games: [{changes_str}] {'liiHappyCat' if total_change > 0 else 'liiCat'}"
        )

    def format_peak_stats(self, player_or_rank, server=None, game_mode="0"):
        """Format peak stats for a player in chat-ready format"""
        player_name, server, error = self._handle_rank_or_name(
            player_or_rank, server, game_mode
        )
        if error:
            return error

        # Resolve alias before lookup
        resolved_name = self._resolve_name(player_name)

        if not server:
            # Find server with highest rating
            response = self.table.scan(
                FilterExpression="PlayerName = :name AND GameMode = :mode",
                ExpressionAttributeValues={":name": resolved_name, ":mode": game_mode},
            )
            items = response.get("Items", [])
            if not items:
                return f"{resolved_name} is not on {server if server else 'any'} BG leaderboards"
            best = max(items, key=lambda x: x["LatestRating"])
            server = best["Server"]

        peak = self.get_player_peak(resolved_name, server, game_mode, hours=None)
        if not peak:
            return f"{resolved_name} has no rating history"

        return (
            f"{resolved_name}'s peak rating in {server} this season: {peak['rating']}"
        )

    def format_player_stats(self, player_or_rank, server=None, game_mode="0"):
        """Format player stats in chat-ready format"""
        player_name, server, error = self._handle_rank_or_name(
            player_or_rank, server, game_mode
        )
        if error:
            return error

        # Resolve alias before lookup
        resolved_name = self._resolve_name(player_name)

        if server:
            # Direct server lookup
            stats = self.get_player_stats(resolved_name, server, game_mode)
            if not stats:
                return f"{resolved_name} is not on {server if server else 'any'} BG leaderboards"
            return f"{resolved_name} is rank {stats['CurrentRank']} in {stats['Server']} at {stats['LatestRating']}"

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
            return f"{resolved_name} is not on {server if server else 'any'} BG leaderboards"

        # Get best rating and other servers
        best = max(items, key=lambda x: x["LatestRating"])
        others = [i for i in items if i["Server"] != best["Server"]]

        if others:
            other = max(others, key=lambda x: x["LatestRating"])
            return (
                f"{resolved_name} is rank {best['CurrentRank']} in {best['Server']} at {best['LatestRating']} "
                f"(also rank {other['CurrentRank']} {other['Server']} at {other['LatestRating']})"
            )

        return f"{resolved_name} is rank {best['CurrentRank']} in {best['Server']} at {best['LatestRating']}"

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
        server = self._parse_server(server)
        if not self._is_valid_server(server):
            return server  # Return error message

        players = self.get_top_players(server, game_mode, limit=10)
        if not players:
            return f"No players found in {server}"

        # Format each player as "name (rating)"
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
                return None, None, f"No player found at rank {rank} in {server}"

            return player["PlayerName"], server, None

        # Handle player name lookup
        except ValueError:
            player_name = player_or_rank
            if server and not self._is_valid_server(server):
                return None, None, server
            return player_name, server, None

    def format_weekly_stats(self, player_or_rank, server=None, game_mode="0"):
        """Format weekly stats for a player in chat-ready format"""
        player_name, server, error = self._handle_rank_or_name(
            player_or_rank, server, game_mode
        )
        if error:
            return error

        # Resolve alias before lookup
        resolved_name = self._resolve_name(player_name)

        # If no server specified, find the one with highest rating
        if not server:
            response = self.table.query(
                IndexName="PlayerLookupIndex",
                KeyConditionExpression="PlayerName = :name AND GameMode = :mode",
                ExpressionAttributeValues={
                    ":name": resolved_name.lower(),
                    ":mode": game_mode,
                })
            items = response.get("Items", [])
            if not items:
                return f"{resolved_name} is not on {server if server else 'any'} BG leaderboards"
            best = max(items, key=lambda x: x["LatestRating"])
            server = best["Server"]

        # Get 7-day history
        history = self.get_player_history(
            resolved_name, server, game_mode, hours=24 * 7
        )
        if not history:
            stats = self.get_player_stats(resolved_name, server, game_mode)
            if not stats:
                return f"{resolved_name} is not on {server if server else 'any'} BG leaderboards"
            return self._format_no_games_response(resolved_name, stats, " this week")

        # A player has games only if they have 2 or more entries
        has_games = len(history) >= 2
        if not has_games:
            stats = self.get_player_stats(resolved_name, server, game_mode)
            return self._format_no_games_response(resolved_name, stats, " this week")

        # Calculate daily deltas using UTC
        daily_changes = [0] * 7
        current_time = datetime.now(timezone.utc)

        for i in range(1, len(history)):
            prev_rating = int(history[i - 1][0])
            curr_rating = int(history[i][0])
            timestamp = int(float(history[i][1]))
            days_ago = (
                current_time - datetime.fromtimestamp(timestamp, timezone.utc)
            ).days
            if 0 <= days_ago < 7:
                daily_changes[days_ago] += curr_rating - prev_rating

        # Calculate total MMR change from start to end
        total_change = int(history[-1][0]) - int(history[0][0])
        total_change_str = f" ({'+' if total_change > 0 else ''}{total_change})"

        # Format daily changes
        daily_str = [
            f"{change:+d}" if change != 0 else "0" for change in reversed(daily_changes)
        ]

        return (
            f"{resolved_name} {'climbed' if total_change > 0 else 'fell'} from {int(history[0][0])} to "
            f"{int(history[-1][0])} ({'+' if total_change > 0 else '-'}{abs(total_change)}) in {server} "
            f"over {len(history) - 1} games: [{', '.join(daily_str)}] {'liiHappyCat' if total_change > 0 else 'liiCat'}"
        )

    def format_milestone_stats(self, rating_threshold, server=None, game_mode="0"):
        """Format milestone stats for chat"""
        try:
            # Validate server first if provided
            if server:
                server = parseServer(server)
                if not server:
                    return "Invalid server. Valid servers are: NA, EU, AP"

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

        except Exception as e:
            logger.error(f"Error getting milestone stats: {str(e)}")
            return "Error getting milestone stats"

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
                    print(f"{title}: {article_url}")
                    return
            else:
                print("No article containing 'battlegrounds' found.")
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")