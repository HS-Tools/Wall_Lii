"""Integration tests against an explicitly selected disposable local database.

RETENTION_TEST_DSN='host=127.0.0.1 port=55439 dbname=hsbg_backup_verify' \
    python -m unittest discover -s tests -p test_player_history_retention.py
"""
import os
from pathlib import Path
import unittest
import psycopg2

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.getenv('RETENTION_TEST_DSN'), 'Requires a disposable local database')
class RetentionTests(unittest.TestCase):
    def connect(self):
        conn = psycopg2.connect(os.environ['RETENTION_TEST_DSN'])
        params = conn.get_dsn_parameters()
        if params.get('host') not in ('127.0.0.1', 'localhost') or not any(
            word in params['dbname'] for word in ('test', 'verify')
        ):
            conn.close()
            self.fail('Refusing to run destructive fixtures outside a local test/verify database')
        return conn

    def test_boundaries_and_statistics(self):
        conn = self.connect()
        try:
            sql = (ROOT / 'scripts/sql/test_player_history_retention.sql').read_text()
            sql = '\n'.join(line for line in sql.splitlines() if not line.startswith('\\'))
            with conn.cursor() as cur:
                cur.execute(sql)
        finally:
            conn.rollback()
            conn.close()

    def test_overlapping_cleanup(self):
        first, second = self.connect(), self.connect()
        try:
            with first.cursor() as lock, second.cursor() as cur:
                lock.execute('SELECT pg_advisory_xact_lock(605019,60)')
                cur.execute('SELECT maintenance.prune_player_history(1)')
                self.assertTrue(cur.fetchone()[0]['skipped'])
        finally:
            first.rollback(); second.rollback()
            first.close(); second.close()

    def test_concurrent_ingestion(self):
        writer, cleaner = self.connect(), self.connect()
        try:
            with writer.cursor() as write, cleaner.cursor() as clean:
                write.execute("""INSERT INTO public.leaderboard_snapshots
                    (player_id,game_mode,region,rating,snapshot_time)
                    SELECT min(player_id),'0','NA',9000,clock_timestamp()+interval '1 hour'
                    FROM public.players RETURNING player_id,snapshot_time""")
                player, timestamp = write.fetchone()
                clean.execute("SET LOCAL statement_timeout='30s'")
                clean.execute('SELECT maintenance.prune_player_history(1)')
                self.assertFalse(clean.fetchone()[0]['skipped'])
                write.execute('SELECT rating FROM public.leaderboard_snapshots WHERE player_id=%s AND snapshot_time=%s',
                              (player, timestamp))
                self.assertEqual(write.fetchone(), (9000,))
        finally:
            writer.rollback(); cleaner.rollback()
            writer.close(); cleaner.close()


if __name__ == '__main__':
    unittest.main()
