-- The situation on a stat line must match the situation on its play.
--
-- /plays/stats repeats each play's down, distance and yards-to-goal on every stat line it
-- emits, so fct_play_stat takes those from the stat row — but its `distance_bucket` and
-- `down_distance_display` are computed in fct_play from fct_play's OWN copy of the same
-- fields. Two sources for one fact, and the derived columns silently follow the second.
--
-- If they ever disagree, the drill-down shows a play labelled "3rd and long" beside a
-- distance of 2, and the filter and the label answer different questions. Rows where the
-- play is absent from fct_play are excluded rather than failed: play-by-play is `recent`
-- scope and a stat line for an unlanded play is a coverage gap, not a contradiction.
--
-- SEVERITY IS WARN, AND THE CURRENT COUNT IS 2. Both are the same play — 401868254879, a
-- Drake reception in 2026 — where CFBD contradicts ITSELF: /plays reports distance 0 and
-- /plays/stats reports 80, which is simply yards_to_goal copied into the wrong field. Both
-- are implausible for a first down, so there is no correct side to prefer and nothing this
-- repo can fix.
--
-- The test earns its keep as a GROWTH DETECTOR rather than a gate. Two rows on one play is
-- an upstream glitch; the same test reading two hundred would mean the two endpoints have
-- genuinely drifted apart, and that is worth knowing before a page renders a mislabelled
-- filter. Error severity here would mean permanently failing the build over a single corrupt
-- upstream record, which is how a real signal gets muted.
{{ config(severity='warn') }}
select s.play_id, s.down as stat_down, p.down as play_down,
       s.distance as stat_distance, p.distance as play_distance,
       s.yards_to_goal as stat_yards_to_goal, p.yards_to_goal as play_yards_to_goal
from {{ ref('fct_play_stat') }} s
join {{ ref('fct_play') }} p on p.play_id = s.play_id
where s.down            is distinct from p.down
   or s.distance        is distinct from p.distance
   or s.yards_to_goal   is distinct from p.yards_to_goal
