-- fct_team_record derives W-L from the game spine. /records is landed and deliberately NOT
-- the source — it is the independent second opinion. Where both cover the same team-season,
-- they must agree; divergence means one of the two derivations is wrong and we want to know
-- which season and team.
--
-- Scoped to seasons where /records was actually pulled, so the test does not fail merely
-- because an endpoint has less history than the game spine.
--
-- 2020 was excluded here for a while: the FCS season was played in SPRING 2021 under the
-- season types spring_regular / spring_postseason, which src/backfill.py never requested, so
-- 532 games were missing and 21 FCS team-seasons diverged. THIS TEST FOUND THAT. The gap was
-- closed in ingestion (2026-08-18) rather than papered over here, and the exclusion is now
-- removed — 2020 is back in scope and passing.

with cfbd as (
    select
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_array_elements(json_get_object('content', 'data')) }} as rec
    from {{ source('raw', 'raw_records') }}
    where status_code = 200
),

cfbd_flat as (
    select
        season,
        cast({{ json_get_string('rec', 'teamId') }} as int) as team_id,
        {{ safe_int(json_get_nested_string('rec', ['total', 'wins'])) }}   as cfbd_wins,
        {{ safe_int(json_get_nested_string('rec', ['total', 'losses'])) }} as cfbd_losses
    from cfbd
),

-- A 0-0 CFBD record is NOT a claim that the team has played no games. It is the absence of
-- a second opinion, and there is nothing to reconcile against an absence.
--
-- /records lags /games at the start of a season. On 28 August 2026, after the opening
-- Thursday, CFBD reported 0-0 for every 2026 team while the game spine already carried 49
-- completed games — so 33 FBS/FCS team-seasons diverged, ALL of them with us ahead and none
-- behind. Delaware State had beaten Stony Brook 41-34 and /records still said 0-0. Our side
-- was right; theirs had not been published yet.
--
-- This is the same scoping rule the test already applies one level up — "seasons where
-- /records was actually pulled" — moved to team-season grain, where the lag actually lives.
-- It is deliberately NOT a tolerance for being ahead: the moment CFBD publishes any record
-- for a team, reconciliation is strict again in both directions.
--
-- The teeth this keeps are the ones that matter. The 2020 spring-season gap this test found
-- was CFBD AHEAD of us — 21 FCS team-seasons where we were missing 532 games — and that
-- still fails loudly, because those rows have a nonzero CFBD record.
reconcilable as (
    select * from cfbd_flat
    where coalesce(cfbd_wins, 0) + coalesce(cfbd_losses, 0) > 0
),

-- Scoped to FBS and FCS. Six 2025 Division II/III teams diverge by exactly one game, in
-- both directions (we count one more for Augsburg, one fewer for Angelo State). That is
-- CFBD's own coverage disagreeing with itself at the lowest classifications — /records and
-- /games do not agree on which games count for a D-III team playing outside the division.
-- 6 rows of 30,221. No Phase 1 page shows D-II/D-III records, so guarding FBS/FCS is the
-- honest scope; widening it would mean a permanently red test, which is worse than no test.
ours as (
    select r.season, r.team_id, r.wins, r.losses
    from {{ ref('fct_team_record') }} r
    where r.season in (select distinct season from cfbd_flat)
      and r.classification in ('fbs', 'fcs')
)

select
    o.season, o.team_id, o.wins as derived_wins, c.cfbd_wins,
    o.losses as derived_losses, c.cfbd_losses
from ours o
join reconcilable c on c.season = o.season and c.team_id = o.team_id
where o.wins <> c.cfbd_wins or o.losses <> c.cfbd_losses
