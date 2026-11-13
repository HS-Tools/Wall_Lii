-- Stop future cleanup, preserving monitoring and the callable maintenance function.
-- Deleted history can only be recovered from a backup.
SELECT cron.unschedule(jobid)
FROM cron.job WHERE jobname = 'player-history-retention-60d';
