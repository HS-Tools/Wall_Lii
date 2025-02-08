import csv
import os
from datetime import datetime, timezone
import functools
import time
from supabase import create_client
from dotenv import load_dotenv

class CommandLogger:
    def __init__(self, log_dir=None):
        # Load environment variables
        load_dotenv()
        
        # Initialize Supabase client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        self.supabase = create_client(url, key)
        
        # Keep log_dir initialization for backward compatibility
        if log_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.log_dir = os.path.join(project_root, "logs", "commands")
        else:
            self.log_dir = log_dir
        self._ensure_log_directory()

    def log_command(self, user, channel, command, full_command, player_name, server, response_time_ms):
        """Log a command execution to Supabase"""
        now = datetime.now(timezone.utc)
        
        # Create the data record matching the table structure
        data = {
            'timestamp': now.isoformat(),
            'created_at': now.isoformat(),
            'user_name': user,          # Changed from 'user' to 'user_name'
            'channel': channel,
            'command': command,
            'full_command': full_command,
            'player_name': player_name or None,  # Use NULL instead of empty string
            'server': server or None,            # Use NULL instead of empty string
            'response_time_ms': response_time_ms
        }
        
        try:
            # Insert the data into the Supabase table
            self.supabase.table('commands').insert(data).execute()
        except Exception as e:
            print(f"Error logging command to Supabase: {e}")

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

# Keep the command_timer decorator unchanged
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
