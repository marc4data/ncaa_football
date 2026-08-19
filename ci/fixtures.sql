-- Minimal raw layer for CI, so dbt models and their tests run on every PR without the
-- 1.6 GB real raw layer.
--
-- Plain SQL rather than dbt seeds on purpose: a seed named `raw_teams` would overwrite the
-- real table if anyone ran `dbt seed` locally, and the fixture is easier to read as the
-- shape it actually is — one row per landed API response, payload in `content`.
--
-- The fixture deliberately spans both eras. 1900 games are stored at midnight UTC as
-- date-only values; 2024 games carry real kickoff times. That is what exercises the
-- per-season era detection in mart_team_schedule, which is where a 66,496-game date shift
-- once hid.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.raw_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_games (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
-- Every landed endpoint has the same shape, so these differ only in name.
CREATE TABLE IF NOT EXISTS raw.raw_venues (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_conferences (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_calendar (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_lines (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_games_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_records (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_model_prediction (
    source_file text NOT NULL, model_version text NOT NULL, prediction_ts timestamptz NOT NULL,
    row_number int NOT NULL, payload jsonb NOT NULL, loaded_at timestamptz DEFAULT now(),
    PRIMARY KEY (source_file, model_version, row_number)
);
CREATE TABLE IF NOT EXISTS raw.raw_deploy_status (
    observed_at timestamptz NOT NULL, deploy_sha text, main_sha text,
    commits_behind int, severity text, detail text,
    PRIMARY KEY (observed_at)
);
CREATE TABLE IF NOT EXISTS raw.raw_games_media (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_rankings (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_season (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_season_advanced (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_dbt_test_result (
    invocation_id text NOT NULL, unique_id text NOT NULL, generated_at timestamptz,
    dbt_version text, status text, failures bigint, execution_time numeric,
    message text, relation_name text,
    PRIMARY KEY (invocation_id, unique_id)
);
CREATE TABLE IF NOT EXISTS raw.raw_info (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_info_usage (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_warehouse_usage (
    observed_at timestamptz NOT NULL, operation text NOT NULL, outcome text,
    elapsed_seconds numeric, catalog text,
    PRIMARY KEY (observed_at, operation)
);
CREATE TABLE IF NOT EXISTS raw.raw_manifest (
    endpoint text NOT NULL, filename text NOT NULL, params jsonb, status_code int,
    row_count int, fetched_at timestamptz, loaded_at timestamptz,
    PRIMARY KEY (endpoint, filename)
);

TRUNCATE raw.raw_teams, raw.raw_games, raw.raw_venues, raw.raw_conferences,
         raw.raw_calendar, raw.raw_lines, raw.raw_games_teams, raw.raw_records,
         raw.raw_info, raw.raw_info_usage, raw.raw_warehouse_usage,
         raw.raw_rankings, raw.raw_stats_season, raw.raw_stats_season_advanced,
         raw.raw_dbt_test_result, raw.raw_model_prediction, raw.raw_games_media,
         raw.raw_deploy_status,
         raw.raw_manifest;

-- Teams, season-scoped. Only year-parameterized fetches feed stg_teams.
INSERT INTO raw.raw_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-00-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 1, "school": "Alpha State", "mascot": "Ones", "abbreviation": "ALP",
     "conference": "Test Conference", "division": null, "classification": "fbs",
     "location": {"city": "Alphaville", "state": "AA"}},
    {"id": 2, "school": "Beta Tech", "mascot": "Twos", "abbreviation": "BET",
     "conference": "Test Conference", "division": null, "classification": "fbs",
     "location": {"city": "Betaburg", "state": "BB"}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:00Z', now()),
('2026-01-01T00-00-00-002Z.json', '{
  "status_code": 200, "params": {"year": "1900"},
  "data": [
    {"id": 1, "school": "Alpha State", "mascot": "Ones", "abbreviation": "ALP",
     "conference": "Old Conference", "division": null, "classification": "fbs",
     "location": {"city": "Alphaville", "state": "AA"}},
    {"id": 2, "school": "Beta Tech", "mascot": "Twos", "abbreviation": "BET",
     "conference": "Old Conference", "division": null, "classification": "fbs",
     "location": {"city": "Betaburg", "state": "BB"}}
  ]}', 200, '{"year": "1900"}', '2026-01-01T00:00:00Z', now()),
-- A failed fetch, landed as the raw layer always does. Staging must filter it out.
('2026-01-01T00-00-00-003Z.json', '{"status_code": 401, "params": {"year": "2024"}, "data": null}',
 401, '{"year": "2024"}', '2026-01-01T00:00:01Z', now());

-- Games. One completed matchup per season, so every reconciliation test has something to
-- reconcile: each game contributes exactly one win and one loss.
INSERT INTO raw.raw_games (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-01-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "startDate": "2024-09-07T23:30:00.000Z", "completed": true, "conferenceGame": true,
     "neutralSite": false, "homeId": 1, "homeTeam": "Alpha State", "homePoints": 28,
     "homeClassification": "fbs", "awayId": 2, "awayTeam": "Beta Tech", "awayPoints": 21,
     "awayClassification": "fbs", "venue": "Alpha Field", "attendance": 50000}
  ]}', 200, '{"year": "2024", "seasonType": "regular"}', '2026-01-01T00:00:02Z', now()),
-- Date-only era: midnight UTC, no kickoff time recorded.
('2026-01-01T00-00-01-002Z.json', '{
  "status_code": 200, "params": {"year": "1900", "seasonType": "regular"},
  "data": [
    {"id": 9002, "season": 1900, "week": 1, "seasonType": "regular",
     "startDate": "1900-11-10T00:00:00.000Z", "completed": true, "conferenceGame": false,
     "neutralSite": false, "homeId": 2, "homeTeam": "Beta Tech", "homePoints": 6,
     "homeClassification": "fbs", "awayId": 1, "awayTeam": "Alpha State", "awayPoints": 5,
     "awayClassification": "fbs", "venue": "Beta Grounds", "attendance": null}
  ]}', 200, '{"year": "1900", "seasonType": "regular"}', '2026-01-01T00:00:03Z', now());

-- The manifest spine: one row per landed response, including the failure.
INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('teams', '2026-01-01T00-00-00-001Z.json', '{"year": "2024"}', 200, 2, '2026-01-01T00:00:00Z', now()),
('teams', '2026-01-01T00-00-00-002Z.json', '{"year": "1900"}', 200, 2, '2026-01-01T00:00:00Z', now()),
('teams', '2026-01-01T00-00-00-003Z.json', '{"year": "2024"}', 401, 0, '2026-01-01T00:00:01Z', now()),
('games', '2026-01-01T00-00-01-001Z.json', '{"year": "2024", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:02Z', now()),
('games', '2026-01-01T00-00-01-002Z.json', '{"year": "1900", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:03Z', now()),
-- An endpoint that has never returned rows: legitimately empty, must not read as a loss.
('records', '2026-01-01T00-00-02-001Z.json', '{"year": "2026"}', 200, 0, '2026-01-01T00:00:04Z', now());

-- ---------------------------------------------------------------------------------------
-- Phase 1 sources. Each carries the smallest payload that exercises a real hazard rather
-- than a happy path — the fixture's job is to fail when a model regresses, not to be
-- representative.
-- ---------------------------------------------------------------------------------------

-- Venues. Stands alone: /games gives a venue *name* and no usable id, so nothing joins here.
INSERT INTO raw.raw_venues (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-03-001Z.json', '{
  "status_code": 200, "params": {},
  "data": [
    {"id": 101, "name": "Alpha Field", "city": "Alphaville", "state": "AA", "zip": "00001",
     "countryCode": "US", "timezone": "America/Chicago", "latitude": 30.5, "longitude": -97.5,
     "elevation": 150.0, "capacity": 50000, "constructionYear": 1950, "grass": true,
     "dome": false},
    {"id": 102, "name": "Beta Grounds", "city": "Betaburg", "state": "BB", "zip": "00002",
     "countryCode": "US", "timezone": "America/New_York", "latitude": 40.1, "longitude": -75.2,
     "elevation": null, "capacity": null, "constructionYear": null, "grass": false,
     "dome": true}
  ]}', 200, '{}', '2026-01-01T00:00:05Z', now());

-- Conferences are season-scoped: the year lives only in params, never in the payload.
INSERT INTO raw.raw_conferences (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-04-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 1, "name": "Test Conference", "shortName": "Test", "abbreviation": "TC",
     "classification": "fbs", "memberCount": 2}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:06Z', now());

-- Calendar. Carries a spring week on purpose: the 2020 FCS season was played in spring 2021
-- under its own season types, and requesting only regular/postseason silently omitted 532
-- real games. A fixture without a spring row lets that regression back in unnoticed.
INSERT INTO raw.raw_calendar (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-05-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "week": 1, "seasonType": "regular",
     "startDate": "2024-08-24T00:00:00.000Z", "endDate": "2024-09-09T00:00:00.000Z",
     "firstGameStart": "2024-08-24T16:00:00.000Z",
     "lastGameStart": "2024-09-08T23:00:00.000Z"},
    {"season": 2024, "week": 1, "seasonType": "postseason",
     "startDate": "2024-12-14T00:00:00.000Z", "endDate": "2025-01-21T00:00:00.000Z",
     "firstGameStart": "2024-12-14T16:00:00.000Z",
     "lastGameStart": "2025-01-20T23:30:00.000Z"}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:07Z', now()),
-- The coverage floor itself. `assert_dim_week_floor_is_2002` asserts equality, not an
-- inequality, so the fixture has to carry the boundary season or the test fails in CI for
-- a reason that has nothing to do with the model. A fixture that asserts a boundary must
-- contain it.
('2026-01-01T00-00-05-003Z.json', '{
  "status_code": 200, "params": {"year": "2002"},
  "data": [
    {"season": 2002, "week": 1, "seasonType": "regular",
     "startDate": "2002-08-24T00:00:00.000Z", "endDate": "2002-09-02T00:00:00.000Z",
     "firstGameStart": "2002-08-24T16:00:00.000Z",
     "lastGameStart": "2002-09-01T23:00:00.000Z"}
  ]}', 200, '{"year": "2002"}', '2026-01-01T00:00:07Z', now()),
('2026-01-01T00-00-05-002Z.json', '{
  "status_code": 200, "params": {"year": "2020"},
  "data": [
    {"season": 2020, "week": 1, "seasonType": "spring_regular",
     "startDate": "2021-02-20T00:00:00.000Z", "endDate": "2021-02-27T00:00:00.000Z",
     "firstGameStart": "2021-02-20T18:00:00.000Z",
     "lastGameStart": "2021-02-26T23:00:00.000Z"},
    {"season": 2020, "week": 1, "seasonType": "spring_postseason",
     "startDate": "2021-04-24T00:00:00.000Z", "endDate": "2021-05-16T00:00:00.000Z",
     "firstGameStart": "2021-04-24T18:00:00.000Z",
     "lastGameStart": "2021-05-15T23:00:00.000Z"}
  ]}', 200, '{"year": "2020"}', '2026-01-01T00:00:07Z', now());

-- Box scores. `possessionTime` arrives as a padded clock string — " 30:15 " with surrounding
-- spaces — which is what broke the integer cast on the real data. Kept verbatim so the
-- split-and-parse path is exercised rather than assumed.
INSERT INTO raw.raw_games_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-06-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "teams": [
      {"teamId": 1, "team": "Alpha State", "homeAway": "home", "points": 28, "stats": [
        {"category": "totalYards", "stat": "412"},
        {"category": "netPassingYards", "stat": "244"},
        {"category": "rushingYards", "stat": "168"},
        {"category": "firstDowns", "stat": "22"},
        {"category": "turnovers", "stat": "1"},
        {"category": "possessionTime", "stat": " 32:41 "}
      ]},
      {"teamId": 2, "team": "Beta Tech", "homeAway": "away", "points": 21, "stats": [
        {"category": "totalYards", "stat": "355"},
        {"category": "netPassingYards", "stat": "301"},
        {"category": "rushingYards", "stat": "54"},
        {"category": "firstDowns", "stat": "19"},
        {"category": "turnovers", "stat": "2"},
        {"category": "possessionTime", "stat": " 27:19 "}
      ]}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:08Z', now());

-- CFBD's own records, for the reconciliation test. Alpha won 9001, Beta lost it, so these
-- agree with what fct_team_record derives from the game spine. A fixture that disagreed
-- would make the test red for a reason that has nothing to do with the code under test.
INSERT INTO raw.raw_records (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-07-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"year": 2024, "teamId": 1, "team": "Alpha State", "classification": "fbs",
     "total": {"games": 1, "wins": 1, "losses": 0, "ties": 0}},
    {"year": 2024, "teamId": 2, "team": "Beta Tech", "classification": "fbs",
     "total": {"games": 1, "wins": 0, "losses": 1, "ties": 0}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:09Z', now()),
-- The legitimately-empty response already in the manifest. An endpoint that returns no rows
-- is not a failure, and nothing downstream may treat it as one.
('2026-01-01T00-00-02-001Z.json', '{
  "status_code": 200, "params": {"year": "2026"}, "data": []
  }', 200, '{"year": "2026"}', '2026-01-01T00:00:04Z', now());

-- Betting lines, two snapshots of the same game.
--
-- Snapshot 1 reproduces the collision that CFBD actually emits: `DraftKings` and
-- `Draft Kings` in one response for one game, identical spread, but the second carrying null
-- moneylines. They are one book, so mapping both to `draftkings` makes the grain collide —
-- and the fixture must contain the collision, or the dedup rule and its losslessness test
-- pass in CI without ever being exercised.
--
-- Two snapshots also mean `fct_betting_line` is built from more than one `snapshot_ts`,
-- which is the minimum needed for the incremental anti-join to mean anything.
INSERT INTO raw.raw_lines (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-08-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "homeTeam": "Alpha State", "awayTeam": "Beta Tech", "lines": [
      {"provider": "DraftKings", "spread": -7.5, "formattedSpread": "Alpha State -7.5",
       "spreadOpen": -7.0, "overUnder": 55.5, "overUnderOpen": 54.5,
       "homeMoneyline": -300, "awayMoneyline": 240},
      {"provider": "Draft Kings", "spread": -7.5, "formattedSpread": "Alpha State -7.5",
       "spreadOpen": -7.0, "overUnder": 55.5, "overUnderOpen": 54.5,
       "homeMoneyline": null, "awayMoneyline": null},
      {"provider": "Bovada", "spread": -7.0, "formattedSpread": "Alpha State -7",
       "spreadOpen": -7.0, "overUnder": 56.0, "overUnderOpen": 55.0,
       "homeMoneyline": -280, "awayMoneyline": 230}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:10Z', now()),
('2026-01-01T00-00-09-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "homeTeam": "Alpha State", "awayTeam": "Beta Tech", "lines": [
      {"provider": "DraftKings", "spread": -8.0, "formattedSpread": "Alpha State -8",
       "spreadOpen": -7.0, "overUnder": 56.5, "overUnderOpen": 54.5,
       "homeMoneyline": -320, "awayMoneyline": 255}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:14Z', now());

-- Manifest rows for the new endpoints. `stg_lines` takes its snapshot timestamp from
-- `fetched_at` here, not from the file, so a lines file with no manifest row is invisible.
INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('venues',      '2026-01-01T00-00-03-001Z.json', '{}', 200, 2, '2026-01-01T00:00:05Z', now()),
('conferences', '2026-01-01T00-00-04-001Z.json', '{"year": "2024"}', 200, 1, '2026-01-01T00:00:06Z', now()),
('calendar',    '2026-01-01T00-00-05-001Z.json', '{"year": "2024"}', 200, 2, '2026-01-01T00:00:07Z', now()),
('calendar',    '2026-01-01T00-00-05-002Z.json', '{"year": "2020"}', 200, 2, '2026-01-01T00:00:07Z', now()),
('calendar',    '2026-01-01T00-00-05-003Z.json', '{"year": "2002"}', 200, 1, '2026-01-01T00:00:07Z', now()),
('games/teams', '2026-01-01T00-00-06-001Z.json', '{"year": "2024", "week": "1", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:08Z', now()),
('records',     '2026-01-01T00-00-07-001Z.json', '{"year": "2024"}', 200, 2, '2026-01-01T00:00:09Z', now()),
('lines',       '2026-01-01T00-00-08-001Z.json', '{"year": "2024", "week": "1", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:10Z', now()),
('lines',       '2026-01-01T00-00-09-001Z.json', '{"year": "2024", "week": "1", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:14Z', now());

-- Quota telemetry. Two snapshots so the series has a delta rather than a single point —
-- one row answers "where are we", only a series answers "where are we heading".
INSERT INTO raw.raw_info (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-10-001Z.json', '{
  "status_code": 200, "params": {},
  "data": {"patronLevel": 3, "tierName": "Tier 3", "monthlyLimit": 75000,
           "remainingCalls": 73053, "usedCalls": 1947,
           "resetAt": "2026-09-01T00:00:00.000Z", "sharedPool": true,
           "products": ["cfb", "cbb"]}
  }', 200, '{}', '2026-01-01T00:00:20Z', now()),
('2026-01-01T00-00-10-002Z.json', '{
  "status_code": 200, "params": {},
  "data": {"patronLevel": 3, "tierName": "Tier 3", "monthlyLimit": 75000,
           "remainingCalls": 72900, "usedCalls": 2100,
           "resetAt": "2026-09-01T00:00:00.000Z", "sharedPool": true,
           "products": ["cfb", "cbb"]}
  }', 200, '{}', '2026-01-01T00:00:21Z', now());

-- The manifest labels this endpoint `info_usage`, not `info/usage`: src/ingest.fetch
-- flattens the slash so the endpoint can be a directory name. Joining on the API path
-- returns zero rows with no error, which is exactly how this model shipped broken once.
INSERT INTO raw.raw_info_usage (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-11-001Z.json', '{
  "status_code": 200, "params": {"days": "31", "limit": "50"},
  "data": {"window": {"start": "2026-07-18T00:00:00.000Z", "end": "2026-08-18T00:00:00.000Z"},
           "api": "cfb",
           "totals": {"requests": 1967, "cfbRequests": 1967, "cbbRequests": 0,
                      "uniqueEndpoints": 65},
           "topEndpoints": [
             {"api": "cfb", "endpoint": "/games", "requests": 324,
              "lastUsedAt": "2026-08-18T00:00:00.000Z"},
             {"api": "cfb", "endpoint": "/rankings", "requests": 203,
              "lastUsedAt": "2026-08-17T00:00:00.000Z"}],
           "recentRequests": []}
  }', 200, '{"days": "31", "limit": "50"}', '2026-01-01T00:00:22Z', now());

-- Warehouse telemetry, including a failed run: a failure burned warehouse time too,
-- usually more, having paid the cold start before dying.
INSERT INTO raw.raw_warehouse_usage (observed_at, operation, outcome, elapsed_seconds, catalog) VALUES
('2026-01-01T00:00:30Z', 'raw_sync', 'success', 5.9,  'workspace'),
('2026-01-01T00:01:00Z', 'dbt_run',  'success', 78.0, 'workspace'),
('2026-01-01T00:02:30Z', 'dbt_test', 'failed',  12.4, 'workspace');

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('info',       '2026-01-01T00-00-10-001Z.json', '{}', 200, 1, '2026-01-01T00:00:20Z', now()),
('info',       '2026-01-01T00-00-10-002Z.json', '{}', 200, 1, '2026-01-01T00:00:21Z', now()),
('info_usage', '2026-01-01T00-00-11-001Z.json', '{"days": "31", "limit": "50"}', 200, 1, '2026-01-01T00:00:22Z', now());

-- Rankings. Three levels of nesting collapse in stg_rankings, so the fixture carries all
-- three: a week, holding two polls, each holding ranks. Two polls on purpose — the compare
-- view's disagreement spread is zero with one, and a zero can hide an arithmetic error.
INSERT INTO raw.raw_rankings (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-12-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "week": 1, "seasonType": "regular", "polls": [
      {"poll": "AP Top 25", "isFinal": false, "ranks": [
        {"rank": 1, "teamId": 1, "school": "Alpha State", "conference": "Test Conference",
         "firstPlaceVotes": 40, "points": 1500},
        {"rank": 2, "teamId": 2, "school": "Beta Tech", "conference": "Test Conference",
         "firstPlaceVotes": 2, "points": 1400}]},
      {"poll": "Coaches Poll", "isFinal": false, "ranks": [
        {"rank": 3, "teamId": 1, "school": "Alpha State", "conference": "Test Conference",
         "firstPlaceVotes": 5, "points": 1300}]}
    ]}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:23Z', now());

-- Season stats. `statValue` is anyOf[string, number] in the OpenAPI spec, so the fixture
-- carries one of each: the numeric cast must survive a string without failing the build.
INSERT INTO raw.raw_stats_season (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-13-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "team": "Alpha State", "conference": "Test Conference",
     "statName": "firstDowns", "statValue": 215},
    {"season": 2024, "team": "Beta Tech", "conference": "Test Conference",
     "statName": "firstDowns", "statValue": 180},
    {"season": 2024, "team": "Alpha State", "conference": "Test Conference",
     "statName": "possessionTime", "statValue": "31:12"}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:24Z', now());

-- dbt's own test outcomes, including a failure: the System Overview page exists to surface
-- failures, so a fixture of nothing but passes would exercise the wrong branch.
INSERT INTO raw.raw_dbt_test_result
  (invocation_id, unique_id, generated_at, dbt_version, status, failures, execution_time, message, relation_name) VALUES
('fixture-invocation-0001', 'test.cfdb_dbt.unique_fct_game_game_sk.abc123',
 '2026-01-01T00:00:25Z', '1.12.0', 'pass', 0, 0.05, NULL, '"cfdb"."marts"."fct_game"'),
('fixture-invocation-0001', 'test.cfdb_dbt.not_null_fct_game_season.def456',
 '2026-01-01T00:00:25Z', '1.12.0', 'fail', 3, 0.07, 'Got 3 results, configured to fail if != 0',
 '"cfdb"."marts"."fct_game"');

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('rankings',     '2026-01-01T00-00-12-001Z.json', '{"year": "2024"}', 200, 1, '2026-01-01T00:00:23Z', now()),
('stats/season', '2026-01-01T00-00-13-001Z.json', '{"year": "2024"}', 200, 3, '2026-01-01T00:00:24Z', now());

-- Model predictions, in the pack's 42-column contract shape.
--
-- The sign convention is the reason these values look backwards and they are correct:
-- margin = away - home, so game 9001 (Alpha 28, Beta 21) has actual_margin = -7 and the
-- HOME team won. A fixture written the intuitive way would make the convention tests pass
-- against wrong data, which is worse than having no fixture at all.
--
-- Row 2 is a week-1 game: the pack trains on regular-season week 5 onward, so this is the
-- out-of-sample case that srv_edge_finder must label rather than render as actionable.
INSERT INTO raw.raw_model_prediction (source_file, model_version, prediction_ts, row_number, payload) VALUES
('linear_margin_predictions.csv', 'fixture00001', '2026-01-01T00:00:40Z', 0, '{
  "game_id": "9001", "season": "2024", "season_type": "regular", "week": "8",
  "home_team": "Alpha State", "away_team": "Beta Tech", "split": "test",
  "model_name": "linear_margin", "model_family": "linear_regression", "target": "margin",
  "home_points": "28", "away_points": "21", "actual_margin": "-7",
  "actual_total_points": "49", "actual_home_win": "True", "actual_winner": "Alpha State",
  "spread": "-4.5", "actual_home_cover": "True",
  "predicted_home_points": "26.5", "predicted_away_points": "22.1",
  "predicted_margin": "-4.4", "predicted_total_points": "48.6",
  "predicted_home_win_probability": "0.64", "raw_home_win_probability": "0.61",
  "calibrated_home_win_probability": "0.64", "predicted_home_win": "True",
  "predicted_winner": "Alpha State", "predicted_home_cover": "False",
  "market_implied_home_win_probability": "0.60",
  "home_win_probability_edge": "0.04", "home_cover_edge": "-0.1",
  "confidence_bucket": "medium", "margin_error": "2.6", "absolute_margin_error": "2.6",
  "home_win_correct": "True", "cover_correct": "False",
  "brier_score_component": "0.1296", "log_loss_component": "0.4463"}'::jsonb),
('linear_margin_predictions.csv', 'fixture00001', '2026-01-01T00:00:40Z', 1, '{
  "game_id": "9003", "season": "2024", "season_type": "regular", "week": "1",
  "home_team": "Beta Tech", "away_team": "Alpha State", "split": "test",
  "model_name": "linear_margin", "model_family": "linear_regression", "target": "margin",
  "home_points": "", "away_points": "", "actual_margin": "",
  "actual_total_points": "", "actual_home_win": "", "actual_winner": "",
  "spread": "3.0", "actual_home_cover": "",
  "predicted_home_points": "20.0", "predicted_away_points": "24.0",
  "predicted_margin": "4.0", "predicted_total_points": "44.0",
  "predicted_home_win_probability": "0.43", "raw_home_win_probability": "0.43",
  "calibrated_home_win_probability": "0.43", "predicted_home_win": "False",
  "predicted_winner": "Alpha State", "predicted_home_cover": "False",
  "market_implied_home_win_probability": "0.46",
  "home_win_probability_edge": "-0.03", "home_cover_edge": "-1.0",
  "confidence_bucket": "low", "margin_error": "", "absolute_margin_error": "",
  "home_win_correct": "", "cover_correct": "",
  "brier_score_component": "", "log_loss_component": ""}'::jsonb);

-- Broadcast media. TWO TV rows for one game on purpose: simulcasts are real (ABC and SEC
-- Network carry the same game), and joining them without deduplication multiplied 18 games
-- into two rows each in fct_game — a silent grain break that still built green. The fixture
-- carries the collision so the dedup is exercised rather than assumed.
INSERT INTO raw.raw_games_media (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-14-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "mediaType": "tv", "outlet": "ABC"},
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "mediaType": "tv", "outlet": "SEC Network"},
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "mediaType": "web", "outlet": "ESPN+"}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:26Z', now());

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('games_media', '2026-01-01T00-00-14-001Z.json', '{"year": "2024"}', 200, 3, '2026-01-01T00:00:26Z', now());

-- Deploy drift. A STALE row on purpose: the alarm exists because production silently ran
-- old code for a day, so the fixture exercises the escalating branch rather than the
-- reassuring one.
INSERT INTO raw.raw_deploy_status
  (observed_at, deploy_sha, main_sha, commits_behind, severity, detail) VALUES
('2026-01-01T00:00:50Z', 'aaaa111', 'bbbb222', 7, 'error',
 'Deploy tree is 7 commits behind main (aaaa111 vs bbbb222). Airflow is running old code');
