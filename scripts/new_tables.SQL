-- 1. leaderboard_snapshots_seasonXX
CREATE TABLE leaderboard_snapshots_seasonXX (
  player_name TEXT NOT NULL,
  game_mode CHAR(1) NOT NULL,         -- 0 = solo, 1 = duo
  region CHAR(2) NOT NULL,
  snapshot_time TIMESTAMPTZ NOT NULL,
  rating SMALLINT NOT NULL,
  rank SMALLINT NOT NULL,
  PRIMARY KEY (player_name, game_mode, region, snapshot_time)
);

-- 2. current_leaderboard_seasonXX
CREATE TABLE current_leaderboard_seasonXX (
  player_name TEXT NOT NULL,
  game_mode CHAR(1) NOT NULL,
  region CHAR(2) NOT NULL,
  rating SMALLINT NOT NULL,
  rank SMALLINT NOT NULL,
  PRIMARY KEY (player_name, game_mode, region)
);

-- 3. milestone_tracking_seasonXX
CREATE TABLE milestone_tracking_seasonXX (
  season SMALLINT NOT NULL,
  game_mode CHAR(1) NOT NULL,
  region CHAR(2) NOT NULL,
  milestone INTEGER NOT NULL,
  player_name TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  rating INTEGER NOT NULL,
  PRIMARY KEY (season, game_mode, region, milestone)
);