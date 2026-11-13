# Player history retention

The database retains 60 rolling days of rating snapshots, plus the newest snapshot
before the cutoff for each player/region/mode (including inactive players). Daily
stats retain today and the preceding 59 dates in America/Los_Angeles. Other tables
are not expired. Existing timestamps determine age; changing `updated_at` does not
renew a row. Cleanup covers every writer, including manual inserts and backfills.

## Installation

Use a PostgreSQL connection as `postgres`; load credentials through environment
variables rather than command-line arguments. Apply these versioned SQL files with
`psql -X -v ON_ERROR_STOP=1 -f FILE`:

1. `scripts/sql/player_history_retention.sql`
2. After backup verification and initial cleanup, `scripts/sql/install_player_history_cron.sql`

Both files are repeatable. The named Cron job runs daily at **10:00 UTC**. Each run
deletes at most 100,000 rows per history table, with a five-minute statement timeout
and five-second lock timeout. An advisory transaction lock prevents overlapping
cleanup; locked rows are skipped and retried next run. Expiration is enforced at
cleanup time, not precisely at each row's 60-day anniversary.

The routine is invoker-security, lives in a private `maintenance` schema, and is not
callable by PUBLIC. Use the SQL Editor as an administrative role for monitoring.
No application ingestion changes, Edge Function, or external scheduler is required.

## Backup before the first deletion

Use a compatible `pg_dump --format=custom` to save the entire database under the
ignored `backups/` directory. Export roles with `pg_dumpall --roles-only
--no-role-passwords`. Keep a SHA-256 manifest and exact row counts using the same
exported repeatable-read snapshot passed to `pg_dump --snapshot`. Keep backups
private and off git. A database dump does not include Storage file contents; export
those separately if any exist.

Restore into a disposable local database and compare every populated table against
the snapshot counts before deleting anything. Native PostgreSQL may lack Supabase
extensions; document those restore errors, never silently accept missing populated
tables. A full Supabase service recovery also needs compatible extensions and
project configuration, which are not provided by a database dump alone.

## Initial cleanup and recovery

With repository dependencies installed and `.env` configured:

```sh
python scripts/prune_supabase.py
python scripts/prune_supabase.py --execute --vacuum
```

The first command previews exact eligible counts. Execution commits batches of
5,000; rerun after interruption or the 200-batch limit. `--batch-size` and
`--max-batches` are configurable. VACUUM ANALYZE runs outside transactions. Ordinary
vacuum makes space reusable but generally does not reduce allocated database size.
Do not use recurring VACUUM FULL; it rewrites and exclusively locks the table.

To stop scheduled deletion, apply `scripts/sql/remove_player_history_cron.sql`.
This preserves maintenance code and logs. Deleted rows require backup recovery;
restore into a separate database first and selectively recover history rather than
overwriting newer live data.

## Monitoring

```sql
SELECT * FROM maintenance.player_history_status;
SELECT * FROM maintenance.player_history_schedule_status;
SELECT * FROM maintenance.player_history_runs ORDER BY id DESC LIMIT 30;
```

Size is reported in bytes; warning starts at 400,000,000 and critical at
450,000,000. `cleanup_status = 'overdue'` means no successful batch in 26 hours.
`batch_limit_reached` means another batch may be needed; rerun the preview to check.
Cron reports SQL failures and timeouts in its run details and the schedule status
view. A successful Cron status alone is insufficient if cleanup was skipped or hit
the batch limit. These are dashboard/query statuses, not push notifications.

Successful runs prune maintenance records and this job's Cron history after 30
days. Other jobs' histories are left alone. Watch the total database size because
other tables, indexes, baseline rows, and internal overhead can still grow; a TTL
does not guarantee a hard 500 MB cap.

## Validation

Install the retention SQL in the restored local test database, then run:

```sh
RETENTION_TEST_DSN='host=127.0.0.1 port=55439 dbname=hsbg_backup_verify' \
  python -m unittest discover -s tests -p test_player_history_retention.py
```

Tests use rollback-only fixtures and cover exact boundaries, Pacific dates/DST,
inactive baselines, batch limits, unchanged daily/weekly aggregates, idempotence,
overlapping cleanup, and concurrent ingestion. Historical recalculation must not
rebuild complete weekly aggregates from a partial week at the retention boundary.
