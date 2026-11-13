"""Preview or run 60-day player-history retention. Preview is the default."""
import argparse
import json
from dotenv import load_dotenv
from db_utils import get_db_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--batch-size', type=int, default=5000)
    parser.add_argument('--max-batches', type=int, default=200)
    parser.add_argument('--vacuum', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100000 or args.max_batches < 1:
        parser.error('batch-size must be 1..100000 and max-batches must be positive')
    if args.vacuum and not args.execute:
        parser.error('--vacuum requires --execute')
    load_dotenv()
    conn = get_db_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5min'")
            cur.execute("SET timezone = 'UTC'")
            if not args.execute:
                cur.execute("""
                    SELECT count(*) FROM public.leaderboard_snapshots old
                    WHERE old.snapshot_time < now() - interval '1440 hours'
                      AND EXISTS (
                        SELECT 1 FROM public.leaderboard_snapshots newer
                        WHERE newer.player_id = old.player_id
                          AND newer.game_mode = old.game_mode AND newer.region = old.region
                          AND newer.snapshot_time > old.snapshot_time
                          AND newer.snapshot_time < now() - interval '1440 hours')
                """)
                snapshots = cur.fetchone()[0]
                cur.execute("""SELECT count(*) FROM public.daily_leaderboard_stats
                    WHERE day_start < (now() AT TIME ZONE 'America/Los_Angeles')::date - 59""")
                print(json.dumps({'preview': True, 'snapshots_to_delete': snapshots,
                                  'daily_rows_to_delete': cur.fetchone()[0]}))
                return
            for batch in range(args.max_batches):
                # Autocommit releases locks and commits every bounded batch separately.
                cur.execute('SELECT maintenance.prune_player_history(%s)', (args.batch_size,))
                result = cur.fetchone()[0]
                print(json.dumps({'batch': batch + 1, **result}), flush=True)
                if result['skipped']:
                    raise RuntimeError('Another cleanup is running; retry later')
                if not result['snapshots_deleted'] and not result['daily_rows_deleted']:
                    break
            else:
                raise RuntimeError('Batch limit reached; rerun to finish cleanup')
            if args.vacuum:
                for table in ('leaderboard_snapshots', 'daily_leaderboard_stats'):
                    cur.execute(f'VACUUM (ANALYZE) public.{table}')
            cur.execute('SELECT row_to_json(s) FROM maintenance.player_history_status s')
            print(json.dumps(cur.fetchone()[0], default=str))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
