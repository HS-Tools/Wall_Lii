-- Apply player_history_retention.sql first. Safe to rerun: named jobs are updated.
CREATE EXTENSION IF NOT EXISTS pg_cron;
-- pg_cron uses UTC on Supabase. Fail rather than silently schedule in another zone.
DO $$ BEGIN
    IF coalesce(current_setting('cron.timezone', true), 'GMT') NOT IN ('GMT', 'UTC') THEN
        RAISE EXCEPTION 'Expected UTC/GMT cron.timezone';
    END IF;
END $$;
SELECT cron.schedule(
    'player-history-retention-60d', '0 10 * * *',
    $job$SET statement_timeout = '5min';
SELECT maintenance.prune_player_history(100000);
DELETE FROM cron.job_run_details
WHERE jobid IN (SELECT jobid FROM cron.job WHERE jobname = 'player-history-retention-60d')
  AND end_time < now() - interval '30 days';$job$
);

CREATE OR REPLACE VIEW maintenance.player_history_schedule_status AS
SELECT j.jobname, j.schedule, j.active, r.status AS last_run_status,
       r.start_time, r.end_time, r.return_message
FROM cron.job j
LEFT JOIN LATERAL (
    SELECT * FROM cron.job_run_details r
    WHERE r.jobid = j.jobid ORDER BY r.runid DESC LIMIT 1
) r ON true
WHERE j.jobname = 'player-history-retention-60d';
REVOKE ALL ON maintenance.player_history_schedule_status FROM PUBLIC;
