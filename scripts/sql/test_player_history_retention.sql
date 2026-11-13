-- ONLY run in a disposable local database with at least two player identities.
-- Apply player_history_retention.sql first. Fixtures are rolled back.
\set ON_ERROR_STOP on
BEGIN;
SET timezone = 'UTC';
TRUNCATE public.leaderboard_snapshots, public.daily_leaderboard_stats;
CREATE TEMP TABLE test_players AS SELECT player_id FROM public.players LIMIT 2;
DO $$
DECLARE r jsonb; reference_time timestamptz := statement_timestamp();
BEGIN
  IF (SELECT count(*) FROM test_players) <> 2 THEN
    RAISE EXCEPTION 'Tests require two player identities';
  END IF;
  INSERT INTO public.leaderboard_snapshots(player_id,game_mode,region,snapshot_time,rating)
  SELECT player_id,'0','NA',reference_time-age,rating FROM test_players
  CROSS JOIN (VALUES (interval '90 days',8000),(interval '61 days',8100),
                     (interval '60 days',8200),(interval '1 day',8300)) f(age,rating);
  INSERT INTO public.leaderboard_snapshots(player_id,game_mode,region,snapshot_time,rating)
  SELECT player_id,'1','EU',reference_time-age,8000 FROM test_players
  CROSS JOIN (VALUES (interval '90 days'),(interval '80 days')) f(age);
  INSERT INTO public.daily_leaderboard_stats
    (player_id,game_mode,region,day_start,rating,rank,games_played,weekly_games_played,day_avg,weekly_avg)
  SELECT player_id,'0','NA',(reference_time AT TIME ZONE 'America/Los_Angeles')::date-age,
    8300,1,2,10,4.5,4.6 FROM test_players CROSS JOIN (VALUES (60),(59),(0)) f(age);
  CREATE TEMP TABLE retained_daily AS SELECT * FROM public.daily_leaderboard_stats
    WHERE day_start >= (reference_time AT TIME ZONE 'America/Los_Angeles')::date-59;
  r := maintenance.prune_player_history(1);
  IF (r->>'snapshots_deleted')::int <> 1 OR (r->>'daily_rows_deleted')::int <> 1 THEN
    RAISE EXCEPTION 'Batch cap failed: %',r;
  END IF;
  PERFORM maintenance.prune_player_history(100000);
  IF (SELECT count(*) FROM public.leaderboard_snapshots) <> 8 THEN
    RAISE EXCEPTION 'Boundary/baseline retention failed';
  END IF;
  IF EXISTS ((SELECT * FROM retained_daily EXCEPT SELECT * FROM public.daily_leaderboard_stats)
    UNION ALL (SELECT * FROM public.daily_leaderboard_stats EXCEPT SELECT * FROM retained_daily)) THEN
    RAISE EXCEPTION 'Retained daily/weekly stats changed';
  END IF;
  IF EXISTS (SELECT 1 FROM public.leaderboard_snapshots
             WHERE game_mode='0' AND snapshot_time < reference_time-interval '61 days') THEN
    RAISE EXCEPTION 'Wrong boundary baseline retained';
  END IF;
  r := maintenance.prune_player_history(100000);
  IF (r->>'snapshots_deleted')::int <> 0 OR (r->>'daily_rows_deleted')::int <> 0 THEN
    RAISE EXCEPTION 'Repeat cleanup was not idempotent';
  END IF;
  BEGIN
    PERFORM maintenance.prune_player_history(0);
    RAISE EXCEPTION 'Invalid batch size accepted';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM <> 'batch_size must be between 1 and 100000' THEN RAISE; END IF;
  END;
  IF ('2026-03-08 07:30+00'::timestamptz AT TIME ZONE 'America/Los_Angeles')::date <> date '2026-03-07'
    OR ('2026-11-01 07:30+00'::timestamptz AT TIME ZONE 'America/Los_Angeles')::date <> date '2026-11-01' THEN
    RAISE EXCEPTION 'Pacific date boundary failed';
  END IF;
END $$;
ROLLBACK;
