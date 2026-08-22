# Reply to Claude Code — reconciliation accepted, proceed to Task 2

Paste the fenced block whole. `cfdb_site_requirements.md` on disk is now **v1.1**, amended against
your reconciliation; changes carry an `[A 08-20]` marker.

---

```
Task 1 did exactly what it was for. Two of my inferences were wrong and you caught them before
either cost a build. The requirements on disk are now v1.1 — re-read the inventory section, Part 5,
and Appendix C (amendment log). Everything I changed is marked [A 08-20].

=== WHAT YOU FOUND, AND WHAT I DID WITH IT ===

The two absent views are the finding that mattered. srv_team_overview and srv_odds_board were marked
"inferred built — page renders" and neither exists. They are now build items 4 and 5 in Part 5.
Team page survives it — the Schedule tab renders from srv_team_game_log and Overview renders
Degraded, which is the per-tab degradation AC-8.2 already required. Odds Board does not survive it:
the whole page IS the provider comparison, so it renders Degraded until the view exists. fct_betting_line
is populated, so that is a view to write, not ingestion.

The framing error is mine and is corrected in the document. "13 of 18 pages render" was a claim about
data readiness that read as a claim about the site. It is not. View built =/= page rendered, and v1.1
now carries both counts separately so they cannot be conflated again. You are right that Task 3 is
not "build 13 pages against existing scaffolding" — it is build the app.

Column renames accepted, built name wins: attribution, snapshot_ts / line_snapshot_ts,
is_out_of_sample_week. One is not a pure rename and I do not want it applied silently:

  is_out_of_sample_week is a WEEK-level flag, not a prediction-level one. Adopted as-is — for
  AC-12.5's purpose it is sufficient and arguably more honest, since out-of-sample-ness is a
  property of the training cut rather than of an individual row. But the UI copy must read
  "out-of-sample week", not "out-of-sample prediction". Those are different claims and only one is
  true.

=== THE THREE UNBUILDABLE CRITERIA — decided ===

1. bucket_n / edge-bucket aggregation. DECIDED: ship Edge Finder degraded now, build the model next.

   You are right that this is a new mart model, not a column. It is also the control I argued
   hardest for — "the one that actually protects you" — so shipping without it needs to be
   deliberate rather than convenient.

   The page ships with the magnitude slider. The hit-rate slider, the n column and the calibration
   panel render DEGRADED, naming fct_edge_bucket_performance. Plus one new criterion, AC-12.3b: the
   page carries a visible statement that edges are currently ranked by magnitude only, with no
   historical reliability filter, and that magnitude alone does not indicate value.

   The rule behind that: a control that is visibly absent is honest; a control that silently
   defaults to 0 is a false protection, which is worse than none. Never ship the hit-rate slider
   defaulted to zero as a stopgap.

   fct_edge_bucket_performance is build item 7. srv_model_performance's games / winner_scored /
   cover_scored are the right denominators to build it from.

2. stat_scope / stat_basis. DECIDED: v1 ships raw team stats only.

   177,876 rows of real team-season stats reach the site this round. The four-way toggle renders
   Degraded naming the missing columns. Opponent scope and adjusted basis are v1.5, build item 8.

   Your publication-boundary call is correct and I want it recorded: adjusted metrics come from
   CFBD's /ratings and /ppa endpoints, NEVER from the pack's training_data.csv. The pack ships those
   features pre-assembled and that is precisely the convenience the provenance rule exists to
   refuse.

3. AC-G.41 false on three of four prediction views. It is now a BUILD ITEM, not a check — item 3 in
   Part 5, ahead of the pages. Join dim_model_version onto srv_edge_finder, srv_matchup and
   srv_today_edges. Do it before or alongside the shared attribution component, because that
   component has nothing to read otherwise.

AC-G.40 — you are right that it was underspecified rather than wrong. Amended to carry its filter:
a view over ~10,000 rows must meet the paint budget WITH its primary key filter applied. srv_matchup
at 110,634 x 65 must never be queried without game_id, and AC-10.1 is revised so arriving with no
game_id renders a game-picker Empty state rather than an unfiltered scan.

=== PROCEED — Task 2, and yes, add the repoint ===

Your recommendation is right and the gate for it is met. Recording why, because this is the case the
freeze rule was written for:

  The evidence-based freeze rule gates a CUTOVER on the parity test passing, not on a date. You have
  245/245 Postgres, 225/225 Databricks, and parity holding on DERIVED VALUES rather than only row
  counts. That satisfies the gate. Repointing the app off mart_* is authorised now, eight days
  before kickoff, and does not wait for 7 September.

  Under the old calendar rule this would have been an argument. Under the evidence rule it is a
  question with an answer. That is the whole point of the change.

So Task 2 is:

  a. The shared foundation, per requirements Part 0 — four-state renderer, status chip, query
     helper, team identity helper, query-param layer, number formatter, attribution component. Build
     each ONCE. This is about two thirds of the value in the requirements and it is the part that
     decays fastest if built per page.
  b. Repoint site/db.py from mart_team_schedule / mart_team_season_record / mart_data_freshness to
     the srv_* equivalents. This is the strangler cutover for the site.
  c. Nav with st.navigation / st.Page in the six wireframe groups. ALL 18 PAGES APPEAR. A page whose
     view does not exist renders Degraded and names it. Do not hide pages you cannot yet fill.
  d. Item 3 above — attribution onto the three prediction views — since (a) depends on it.

Then items 4 and 5: srv_team_overview and srv_odds_board.

Stop and report after Task 2. Page building is the next round and it is large enough to deserve its
own.

=== ONE THING I WANT IN THE REPORT ===

For the four-state renderer, show each of the four states actually rendering — not a description of
them. Forced Empty, forced Degraded, forced Error, and the Loading skeleton at correct height. The
states are most of what the requirements are about, and they are the part that is easiest to claim
and hardest to verify from a diff.
```

---

## What changed in v1.1, in one place

44 marked amendments. The ones that change what gets built:

| Change | Effect |
|---|---|
| `srv_team_overview`, `srv_odds_board` absent | Two new build items; Odds Board is now Blocked, Team page partly |
| "13 of 18 render" corrected | Two counts now stated separately — views built vs pages rendered |
| Edge Finder ships without its calibration layer | AC-12.1/12.2/12.3/12.9 revised, AC-12.3b added |
| Stats ships raw-only | AC-6.1 revised, AC-6.2 deferred to v1.5 |
| AC-G.41 reclassified as a build item | It was false, not unmet |
| AC-G.40 carries its filter | `srv_matchup` unfiltered would never have met it |
| Three column renames | `attribution`, `snapshot_ts`, `is_out_of_sample_week` |
| Part 5 rewritten | Steps 0–6 marked done with evidence; nine remaining items, app-first |

All 209 acceptance criteria are preserved — none were dropped, one was retired in place (AC-4.1,
whose Degraded state is now unreachable) and one added. Numbering is stable, so any reference to an
AC number from a previous round still resolves.
