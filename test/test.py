import sys
sys.path.append("../src")
sys.path.append("../lambda-loader/src")
import data
from default_alias import alias as default_alias
from default_channels import channels as default_channels
from leaderboardBot import LeaderBoardBot


def setup_production_environment(database, url):
    tables = [table.name for table in database.resource.tables.all()]

    if 'player-alias-table' not in tables:
        database.create_support_table('player-alias-table', 'Alias')

    if 'channel-table' not in tables:
        database.create_support_table('channel-table', 'ChannelName')

    if 'daily-rating-record-table' not in tables:
        database.create_table('daily-rating-record-table')

    if 'yesterday-rating-record-table' not in tables:
        database.create_table('yesterday-rating-record-table')


