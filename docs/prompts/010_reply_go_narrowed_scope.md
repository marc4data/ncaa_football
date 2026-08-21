# Reply to Claude Code — GO. Start A1 now.

Paste the fenced block whole. Requirements on disk are **v1.3**.

---

```
Start step A1 now under your narrowed scope. Everything below is confirmation, not new instruction —
read it after you've begun.

Your recommendation is adopted verbatim. You were right that step 1 depended on steps 6-8, right
that srv_team_overview was the sharpest case of it, and right that the fix is to narrow the scope
rather than abandon the one-pass shape. Three review rounds is two more than this should have taken
and the cause was mine: I wrote the spec from assumed state three times. You have corrected it three
times. That is not a sustainable division of labour and I am not adding a fourth round.

=== WHAT v1.3 CHANGED ===

Build order is now TWO TRACKS. Track B does not gate Track A.

  TRACK A — the site
    A1  Serving completeness pass, one PR, complete WITH RESPECT TO BUILT FACTS
    A2  Publish serving to the droplet AND repoint the app — ONE DEPLOY (see below)
    A3  Shared foundation
    A4  Build the 18 pages

  TRACK B — the facts, in parallel, gating nothing
    B1 fct_team_week_rating   B2 fct_game_weather   B3 venue join key
    B4 talent + returning production   B5 dim_coach   B6 fct_edge_bucket_performance
    B7 CFBD adjusted metrics   B8 the four player tables

The contract is restated so it means something: "complete with respect to facts that exist today."
Anything sourced from an unbuilt fact renders Degraded, naming the fact. You are right that without
that restatement, "no partially-contracted serving layer" was unachievable until step 8 anyway and
the phrase was protecting nothing.

A1 in scope, per your list: team_slug + display names + contrast colours on dim_team, as_of_ts
everywhere, start_date_et, records, ranks from fct_poll_rank, attribution + model_version_key,
segment_type/segment_value, description_status, is_upset (NEW COLUMN, not assumed — thank you),
excitement_index from the 112,272 raw games, network from the landed raw/games_media (invisible in
every prior build order — also thank you), and srv_odds_board IN FULL since fct_betting_line has no
deferred dependency.

srv_team_overview builds NARROWED: identity, record, conference standing, ATS. Its ratings and
profile block renders Degraded naming fct_team_week_rating.

=== THE THREE THINGS I DECIDED RATHER THAN DEFERRED ===

1. A2 IS ONE DEPLOY. You caught that scoping cfdb_read to serving and revoking marts breaks the
   running app the instant it lands. v1.2 had them as separate steps, which was wrong. Publish,
   repoint, re-scope the role — one deploy, or strictly ordered inside one. Do not merge a role
   change that lands ahead of the repoint.

2. prediction_interval_low/high: DO NOT DERIVE IT. You grepped the contract and it appears zero
   times. AC-8.5's own reasoning is exactly why not — a bare point estimate overstates what an
   11.75-point MAE knows, and an interval nobody's model produced would be a confidence claim
   invented to satisfy a document. AC-8.5 is amended: render the point estimate with the model's MAE
   stated immediately beside it. Honest today, and it upgrades itself the day a quantile model
   ships. If you disagree and think an MAE-derived band is defensible, say so — but ship the MAE
   version first either way.

3. fct_team_week_rating MOVES TO B1. I have deferred it four rounds on "primary on zero pages."
   That reasoning was right about blocking and wrong about value. It blocks nothing and it is the
   single largest source of Degraded sections across the finished site — four pages, and the
   most-quoted numbers on each. It is the first fact to build once A1 is out.

=== AC-G.56 — my defect, fixed ===

You were right that ten page sections still carried v1.1's "Status. Renders." under a criterion that
calls a stale readiness line a defect. All 18 now carry Exists / Complete / Published. Published is
✗ on every page until A2 lands, which is the honest state and makes the dependency visible.

=== WHAT I DID NOT TOUCH ===

Part 0. Third reconciliation, still no changes. It is the only part of this document written from
first principles rather than from assumed state, and it is the only part that has never been wrong.
I am taking that as the lesson rather than as a coincidence.

=== FROM HERE ===

Track A is yours to run without waiting on me. If something in A1 turns out to depend on a fact that
is not built, move it out of scope and into Track B yourself and note it in the report — do not stop
for a decision. The only things worth a round-trip now are licence questions and anything that would
put a number on screen the model did not produce.

Report on A1: column-completeness output per view (present/missing), parity across both engines,
and ROW COUNTS BEFORE AND AFTER per view. A widening that accidentally introduces a fan-out shows up
as a row count, not an error — srv_matchup should still be 110,634 and srv_team_stats 177,876 on
both sides.
```
