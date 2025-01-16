import csv
import os
from datetime import datetime, timezone
import functools
import time

class CommandLogger:
    def __init__(self, log_dir=None):
        if log_dir is None:
            # Get the project root directory (parent of src)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.log_dir = os.path.join(project_root, "logs", "commands")
        else:
            self.log_dir = log_dir
        self._ensure_log_directory()
        self.current_file = None
        self.current_date = None
        self.csv_writer = None
        self.csv_file = None

    def _ensure_log_directory(self):
        """Ensure the log directory exists"""
        os.makedirs(self.log_dir, exist_ok=True)

    def _get_log_filename(self, date):
        """Get the log filename for a specific date"""
        return os.path.join(self.log_dir, f"commands_{date.strftime('%Y_%m_%d')}.csv")

    def _ensure_file_open(self):
        """Ensure we have the correct log file open"""
        current_date = datetime.now(timezone.utc).date()
        
        # If we need to switch to a new file
        if self.current_date != current_date:
            if self.csv_file:
                self.csv_file.close()
            
            filename = self._get_log_filename(current_date)
            file_exists = os.path.exists(filename)
            
            self.csv_file = open(filename, 'a', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            
            # Write header if new file
            if not file_exists:
                self.csv_writer.writerow([
                    'timestamp',
                    'user',
                    'channel',
                    'command',
                    'full_command',
                    'player_name',
                    'server',
                    'response_time_ms'
                ])
            
            self.current_date = current_date

    def log_command(self, user, channel, command, full_command, player_name, server, response_time_ms):
        """Log a command execution"""
        self._ensure_file_open()
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        self.csv_writer.writerow([
            timestamp,
            user,
            channel,
            command,
            full_command,
            player_name or '',  # Use empty string if None
            server or '',       # Use empty string if None
            response_time_ms
        ])
        self.csv_file.flush()  # Ensure it's written to disk

def command_timer(func):
    """Decorator to time command execution"""
    @functools.wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        start_time = time.time()
        try:
            result = await func(self, ctx, *args, **kwargs)
            return result
        finally:
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)  # Convert to milliseconds
            
            # Extract command name from the decorated function
            command = ctx.message.content.split()[0].lstrip('!')
            
            # Get player name and server from args if available
            player_name = None
            server = None
            
            if args:
                # Try to get player_name and server from common command patterns
                if len(args) >= 2:
                    player_name = str(args[0])
                    server = str(args[1])
                elif len(args) == 1:
                    player_name = str(args[0])
            
            # Log the command
            self.command_logger.log_command(
                user=ctx.author.name,
                channel=ctx.channel.name,
                command=command,
                full_command=ctx.message.content,
                player_name=player_name,
                server=server,
                response_time_ms=response_time
            )
    
    return wrapper
