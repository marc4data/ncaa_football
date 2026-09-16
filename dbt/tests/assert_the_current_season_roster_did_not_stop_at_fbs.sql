{{ config(severity='warn', tags=['full_refresh_only']) }}
-- 🚨 THE ROSTER THAT STOPPED IN AUGUST — A151, cfdb-main-R-1035.
--
-- 📊 WHAT HAPPENED, AND IT IS §2.5's ASYMMETRY EXACTLY. `/roster` is fetched ONCE per season and
-- nothing re-fetches it: it sits in `BUCKET_STRUCTURAL`, and **no refresh callable in
-- `src/weekly.py` expands that bucket at all** — `results_refresh` takes IMMUTABLE_WK and
-- REVISIONIST, `pregame_refresh` takes PREGAME. That is deliberate for data that does not change.
--
-- ⚠️ BUT THE SOURCE PUBLISHES IT PROGRESSIVELY. The 2026 fetch ran on 2026-08-15, twelve days
-- before the season opened, and CFBD had **FBS only** at that moment: 15,442 athletes across
-- **138 teams, every one FBS**, against 2025's 30,072 across 305. Re-requested on 2026-09-16 the
-- same call returned **31,070 athletes across 306 teams**. Nothing failed; nothing retried.
--
-- 🚨 AND IT RENDERED AS AN HONEST-LOOKING ABSENCE FOR THREE WEEKS. `srv_player_game_log` LEFT
-- joins `dim_athlete`, so half of Today's leaderboards said *"cfdb holds no roster row for this
-- player's team this season"* — a true sentence about a fixable gap. **A missing column fails
-- loudly; a NULL one does not, which is the whole of §2.5.**
--
-- ── WHY THE PRIOR SEASON IS THE YARDSTICK AND "TEAMS THAT PLAYED" IS NOT ────────────────────
--
-- 📊 MEASURED: even a healthy season rosters only ~43% of the teams that appear in
-- `fct_game_team`, because that relation carries every OPPONENT — NAIA and non-member programs
-- cfbd holds no roster for and never will. 2024 42.1%, 2025 43.6%, 2026 43.5% after the backfill.
-- **A threshold on that ratio would sit at 42% and could not tell a healthy season from a broken
-- one**, because the broken one was 19.9% of the same denominator and a hurricane-shortened
-- season could plausibly land between them.
--
-- ✅ THE PRIOR SEASON'S OWN COUNT IS SELF-CALIBRATING and needs no constant anyone has to defend:
--
--     2025 vs 2024   305 vs 298   102.3%   ✅
--     2026 vs 2025   301 vs 305    98.7%   ✅  (after A151's backfill)
--     2026 vs 2025   138 vs 305    45.2%   🚨  (what stood for three weeks)
--
-- ⚠️ 80% IS THE BOUND AND IT IS A GRAIN RESTATED RATHER THAN A GUESS (AC-G.39): the count is the
-- number of PROGRAMS the source rosters, which moves by a handful of teams a year — the three
-- real comparisons span 98.7% to 102.3%. **A season that loses a fifth of its programs has had
-- something happen to it.**
--
-- 🚨 R-760 — WHAT WOULD HAVE TO BE WRONG FOR THIS TO FIRE: it fired for eighteen days, from the
-- first completed 2026 game on 2026-08-29 until this round's backfill. It is not decoration and
-- it is not true by construction.
--
-- ⚠️ `severity='warn'`, DELIBERATELY, AND THE REASON IS §2.3. `dbt_test` GATES `publish` on both
-- partial DAGs, so an `error` here would stop the site publishing over a roster gap that makes a
-- tooltip thinner — A148's R-1016 lesson, that a control which halts the site over something
-- cosmetic is worse than the thing it guards. ✅ **AND A WARN IS READ HERE**: every result lands
-- in `fct_dq_test_result` and `srv_system_health` publishes it, which is how this round confirmed
-- that `assert_play_stat_situation_agrees_with_the_play` has warned with exactly 2 failures since
-- 2026-09-03. A warn in this project is a signal, not a shrug.
--
-- ⚠️ ONLY A SEASON THAT HAS PLAYED. Before kickoff an incomplete roster is the source still
-- publishing, not a defect — and this test must not fire every August on a season that is simply
-- not there yet.
with rostered as (

    select season, count(distinct team_id) as teams
    from {{ ref('dim_athlete') }}
    group by season

),

played as (

    select distinct season
    from {{ ref('fct_game_team') }}
    where is_completed

),

comparable as (

    -- The join to `prior` is what skips the earliest rostered season: 2023 has no roster at all,
    -- so 2024 has nothing to be compared against and is correctly silent rather than assumed.
    select r.season, r.teams, prior.teams as prior_teams
    from rostered r
    join rostered prior
      on prior.season = r.season - 1 and prior.teams > 0
    join played p on p.season = r.season

)

select
    season,
    teams        as teams_rostered,
    prior_teams  as teams_rostered_last_season,
    round(100.0 * teams / prior_teams, 1) as pct_of_prior_season,
    'the roster covers far fewer programs than last season — /roster is BUCKET_STRUCTURAL and '
    'nothing re-fetches it, so a fetch that ran before the source was complete stays incomplete'
        as rule
from comparable
where teams < prior_teams * 0.80
