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
    {{ surrogate_key(['r.season', 'r.season_type', 'r.week', 'r.team_id']) }} as rankings_compare_sk,
    r.season,
    r.season_type,
    r.week,
    r.team_id,
    r.school,
    -- A170 (cfdb-main-R-1322). THE SLUG, SO THE TEAM NAME ON THIS TAB CAN BE A LINK LIKE EVERY
    -- OTHER TEAM NAME ON THE PAGE. A169 made the name a link on Standings, Rankings and Stats
    -- and this tab was the one it could not reach: the view carried `school` and `team_id` and
    -- no slug, checked against information_schema rather than against the model file.
    --
    -- The macro, not a hand-rolled join, and its fallback is the reason: /games knows who
    -- played, /teams knows who is an FBS program, and the first set is larger. srv_rankings
    -- measured 662 of 49,798 rows (1.3%) with no dim_team row. A null slug is a link to
    -- nowhere, which is worse than a name that was never clickable.
    {{ team_identity('t', 'r.school') }},
    r.conference_name,
    r.ap_rank,
    r.coaches_rank,
    r.committee_rank,
    -- greatest/least ignore nulls in both dialects, so a team ranked in only one poll
    -- yields a zero spread rather than a null row.
    greatest(coalesce(r.ap_rank, r.coaches_rank, r.committee_rank),
             coalesce(r.coaches_rank, r.ap_rank, r.committee_rank),
             coalesce(r.committee_rank, r.ap_rank, r.coaches_rank))
      - least(coalesce(r.ap_rank, r.coaches_rank, r.committee_rank),
              coalesce(r.coaches_rank, r.ap_rank, r.committee_rank),
              coalesce(r.committee_rank, r.ap_rank, r.coaches_rank)) as disagreement_spread,
    ao_src.as_of_ts
from ranked r
-- Same join as srv_rankings uses, on the same two columns, so the two tabs of one page cannot
-- resolve the same team to different identities.
left join {{ ref('dim_team') }} t on t.season = r.season and t.team_id = r.team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'rankings') ao_src
