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
CREATE TABLE IF NOT EXISTS raw.raw_manifest (
    endpoint text NOT NULL, filename text NOT NULL, params jsonb, status_code int,
    row_count int, fetched_at timestamptz, loaded_at timestamptz,
    PRIMARY KEY (endpoint, filename)
);

TRUNCATE raw.raw_teams, raw.raw_games, raw.raw_venues, raw.raw_conferences,
         raw.raw_calendar, raw.raw_lines, raw.raw_games_teams, raw.raw_records,
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
