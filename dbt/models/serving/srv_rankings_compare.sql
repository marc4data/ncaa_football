-- Rankings page, comparison tab: one row per team x season x week, one column per poll.
--
-- Pivoted in dbt rather than in the app, per the serving contract — Streamlit does a single
-- SELECT with a WHERE and no math. The pivot is over the two polls that run the full modern
-- era; committee rankings are included because disagreement with the committee is the most
-- interesting column on the page.
--
-- `disagreement_spread` is the point of the tab: the largest gap between any two polls
-- ranking the same team, which is what makes a row worth looking at.
with ranked as (
    select
        season, season_type, week, team_id, school, conference_name,
        max(case when poll_name = 'AP Top 25' then rank end)                  as ap_rank,
        max(case when poll_name = 'Coaches Poll' then rank end)               as coaches_rank,
        max(case when poll_name = 'Playoff Committee Rankings' then rank end) as committee_rank
    from {{ ref('fct_poll_rank') }}
    where rank is not null
    group by season, season_type, week, team_id, school, conference_name
)
select
    {{ surrogate_key(['season', 'season_type', 'week', 'team_id']) }} as rankings_compare_sk,
    season,
    season_type,
    week,
    team_id,
    school,
    conference_name,
    ap_rank,
    coaches_rank,
    committee_rank,
    -- greatest/least ignore nulls in both dialects, so a team ranked in only one poll
    -- yields a zero spread rather than a null row.
    greatest(coalesce(ap_rank, coaches_rank, committee_rank),
             coalesce(coaches_rank, ap_rank, committee_rank),
             coalesce(committee_rank, ap_rank, coaches_rank))
      - least(coalesce(ap_rank, coaches_rank, committee_rank),
              coalesce(coaches_rank, ap_rank, committee_rank),
              coalesce(committee_rank, ap_rank, coaches_rank)) as disagreement_spread,
    ao_src.as_of_ts
from ranked
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'rankings') ao_src
