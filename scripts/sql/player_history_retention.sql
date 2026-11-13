-- Run as postgres. Private maintenance objects are not exposed through PostgREST.
BEGIN;
CREATE SCHEMA IF NOT EXISTS maintenance;
REVOKE ALL ON SCHEMA maintenance FROM PUBLIC;

CREATE TABLE IF NOT EXISTS maintenance.player_history_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ran_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    snapshot_cutoff timestamptz NOT NULL,
    daily_cutoff date NOT NULL,
    snapshots_deleted integer NOT NULL,
    daily_rows_deleted integer NOT NULL,
    database_bytes bigint NOT NULL,
    duration_ms numeric NOT NULL,
    batch_limit_reached boolean NOT NULL
);
REVOKE ALL ON maintenance.player_history_runs FROM PUBLIC;

CREATE OR REPLACE FUNCTION maintenance.prune_player_history(batch_size integer DEFAULT 5000)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = pg_catalog, maintenance
SET timezone = 'UTC'
SET lock_timeout = '5s'
AS $$
DECLARE
    started timestamptz := clock_timestamp();
    cutoff timestamptz := statement_timestamp() - interval '1440 hours';
    first_day date := (statement_timestamp() AT TIME ZONE 'America/Los_Angeles')::date - 59;
    snapshots integer;
    daily_rows integer;
    bytes bigint;
BEGIN
    IF batch_size IS NULL OR batch_size < 1 OR batch_size > 100000 THEN
        RAISE EXCEPTION 'batch_size must be between 1 and 100000';
    END IF;
    IF NOT pg_try_advisory_xact_lock(605019, 60) THEN
        RETURN jsonb_build_object('skipped', true, 'reason', 'cleanup already running');
    END IF;

    -- Keep the newest pre-cutoff snapshot for EVERY player/mode/region,
    -- including inactive players. New ingestion cannot invalidate this baseline.
    WITH candidates AS (
        SELECT old.ctid
        FROM public.leaderboard_snapshots old
        WHERE old.snapshot_time < cutoff
          AND EXISTS (
              SELECT 1 FROM public.leaderboard_snapshots newer
              WHERE newer.player_id = old.player_id
                AND newer.game_mode = old.game_mode
                AND newer.region = old.region
                AND newer.snapshot_time > old.snapshot_time
                AND newer.snapshot_time < cutoff
          )
        LIMIT batch_size
        FOR UPDATE OF old SKIP LOCKED
    )
    DELETE FROM public.leaderboard_snapshots s
    USING candidates c WHERE s.ctid = c.ctid;
    GET DIAGNOSTICS snapshots = ROW_COUNT;

    WITH candidates AS (
        SELECT ctid FROM public.daily_leaderboard_stats
        WHERE day_start < first_day
        LIMIT batch_size
        FOR UPDATE SKIP LOCKED
    )
    DELETE FROM public.daily_leaderboard_stats d
    USING candidates c WHERE d.ctid = c.ctid;
    GET DIAGNOSTICS daily_rows = ROW_COUNT;

    bytes := pg_database_size(current_database());
    INSERT INTO maintenance.player_history_runs
        (snapshot_cutoff, daily_cutoff, snapshots_deleted, daily_rows_deleted,
         database_bytes, duration_ms, batch_limit_reached)
    VALUES (cutoff, first_day, snapshots, daily_rows, bytes,
            extract(epoch FROM clock_timestamp() - started) * 1000,
            snapshots = batch_size OR daily_rows = batch_size);
    DELETE FROM maintenance.player_history_runs
    WHERE ran_at < statement_timestamp() - interval '30 days';

    RETURN jsonb_build_object('skipped', false, 'snapshots_deleted', snapshots,
        'daily_rows_deleted', daily_rows, 'database_bytes', bytes,
        'batch_limit_reached', snapshots = batch_size OR daily_rows = batch_size);
END;
$$;
REVOKE ALL ON FUNCTION maintenance.prune_player_history(integer) FROM PUBLIC;

CREATE OR REPLACE VIEW maintenance.player_history_status AS
SELECT pg_database_size(current_database()) AS database_bytes,
       CASE WHEN pg_database_size(current_database()) >= 450000000 THEN 'critical'
            WHEN pg_database_size(current_database()) >= 400000000 THEN 'warning'
            ELSE 'ok' END AS size_status,
       r.ran_at AS last_success_at,
       CASE WHEN r.ran_at IS NULL OR r.ran_at < now() - interval '26 hours'
            THEN 'overdue' ELSE 'ok' END AS cleanup_status,
       r.snapshots_deleted, r.daily_rows_deleted, r.batch_limit_reached
FROM (SELECT 1) anchor
LEFT JOIN LATERAL (
    SELECT * FROM maintenance.player_history_runs ORDER BY id DESC LIMIT 1
) r ON true;
REVOKE ALL ON maintenance.player_history_status FROM PUBLIC;
COMMIT;
