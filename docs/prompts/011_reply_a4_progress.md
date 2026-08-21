# Reply to Claude Code — keep going, plus three things from the sample review

Paste the fenced block whole. Requirements amended: Excel Export is now **A5**, its own task; a
deploy-tree staleness guard is **A6**.

---

```
Nine of eighteen rendering. Keep going — nothing below changes what you're doing next.

=== THE MOST VALUABLE THING IN THIS ROUND WAS THE G-2 CATCH ===

  where team = (select max(team_display) from srv_team_overview ...)

Two relations in one query, wearing a filter's clothing. No review would have caught that — it does
not contain the word JOIN, it reads as a scalar, and the intent behind it was reasonable. Your own
contract test caught it, which is the entire argument for putting AC-G.1 to G.3 in code rather than
in a checklist, and it is now proven rather than asserted.

Same for finding that srv_rankings_compare keys on school rather than team_display. Found by running
it, not by reading it. That is the difference between the two modes and it is worth saying plainly:
I have been wrong four times on this project, every time by reading rather than running.

=== AGREED: Excel Export becomes its own task ===

You are right and it is now A5, split out of A4. Three reasons, all yours: 12 acceptance criteria, a
workbook generator rather than a page, and the closest thing on the site to the licence line.
Tailing it onto A4 guarantees it gets the least attention, and it is the one deliverable where the
boundary is a judgement call rather than a structural fact. A4 is now 17 pages.

=== THE AIRFLOW FINDING DESERVES A GUARD, NOT JUST A FIX ===

Production ran PR #17 while development reached #19 — the nightly Databricks sync and the weekly
refreshes were building a dbt project with NONE of A1 in it. 39 models instead of 56.

Worth naming what happened: the worktree pin fixed "a dev checkout silently changes production
scheduling" and created its mirror image, "production silently keeps running old code." Both are the
deploy tree and the dev tree diverging; the pin changed which direction it runs. Pinning to main
means someone has to actively move the pin, and that is a manual step with no alarm on it.

deploy_main.sh is the step. Add the alarm as A6, and put it where the page already exists:
srv_system_health carries signal_type values freshness / data_quality / documentation / quota. Add
DEPLOYMENT — deploy SHA, main SHA, commits behind, severity escalating past a threshold. Small, and
it belongs to System Overview whenever you build that page.

A divergence that is visible is an inconvenience. This one was invisible.

=== THREE THINGS FROM srv_sample.xlsx THAT AFFECT PAGES YOU ALREADY SHIPPED ===

Full review is in ../claude_work/cfdb_srv_sample_review.md. Three items land on Today, Teams and
Team page, which are now live rather than hypothetical:

1. LOGOS ARE 0% POPULATED IN EVERY VIEW THAT CARRIES THEM.
   logo_url, home_logo_url, away_logo_url, logo_source_url, logo_path — null on every sampled row of
   all six views. Not a season artefact; srv_teams_index and srv_team_overview are team-grain and
   still empty.

   So Teams (681 cards) and Today (211 games) are rendering the AC-G.28 monogram fallback 100% of
   the time. That is not a bug in your pages — they are doing the right thing — but if the fallback
   always fires then it is the design rather than the safety net, and the site has no logos at all.
   One dbt change unblocks AC-G.27 and G.28 across six views.

2. ats_record_display RENDERS "0-0-0" FOR A SEASON THAT HAS NOT STARTED.
   851 of 1,000 sampled srv_team_overview rows — every 2026 team. In the SAME ROW, wins, losses and
   record_display are correctly null. One table, two treatments of "hasn't happened yet."

   AC-G.32 and AC-G.6 exactly. A user reading 0-0-0 sees a team that has gone 0-0-0, not a season
   that has not begun. Same for ats_wins/losses/pushes and the favourite/underdog displays at "0-0".
   Team page is live, so this is on screen now.

3. THE WEEK-5 FLOOR — and I had this wrong, so read this one carefully.
   I initially flagged "no 2026 predictions" as an emergency. It is not. CFBD does not ship 2026
   feature files until Week 5, because the models need several weeks of current-season results
   before they can forecast this year's teams. The models are trained. Weeks 1-4 having no
   predictions is BY DESIGN and recurs every season.

   The rule is already in your data: srv_edge_finder.training_week_floor = 5, constant. It is ABSENT
   from srv_today_edges and srv_matchup — the two views that will be empty for four weeks and have
   to explain why. Add it to both, so the empty state is data-driven rather than a hardcoded "Week
   5" string.

   This is EMPTY, not Degraded. Degraded means we have not built it; Empty means the data does not
   exist yet and here is why. Suggested copy, and it is worth writing well because it recurs every
   season: "Model predictions begin in Week 5. The 2026 model needs several weeks of current-season
   results before it can forecast this year's teams." That is a credibility asset — a model that
   refuses to guess before it knows anything.

   Practical effect on A4: Odds Board and Line Movement are unaffected (pure market). Matchup
   renders everything but the model block. Edge Finder is the ONLY page with nothing to show for the
   first four weeks, since an edge is model minus market — it carries the explanation as its whole
   page. Do not hide it (AC-G.51).

   Also in the review, lower priority: srv_model_performance still has no segment_type/segment_value,
   so Model Performance's by-week, by-conference and calibration sections have no source; four of six
   models have cover_scored = 0 and must render em-dash, never 0.0%; and slugs are missing from
   srv_teams_index, srv_standings, srv_team_game_log, srv_scoreboard and srv_matchup.

=== THE UNCOMMITTED FILES ===

Being precise about provenance rather than accepting the label: I have never written to the
claude_code tree in any session. Cowork owns claude_work and produces no production code. The only
claude_code path I have touched is READING config/api-docs.json.

So I cannot tell you what created requirements.txt's openpyxl line or tests/test_data_dictionary.py.
Marc decides. My read on what they are:

  config/api-docs.json          the CFBD OpenAPI v5.24.0 spec. It is the upstream input to
                                cfdb_data_dictionary.xlsx and to dim_field_metadata. Worth keeping.
  requirements.txt (openpyxl)   needed for the Excel export (A5) and for generating srv_sample.xlsx.
                                Presumably yours.
  tests/test_data_dictionary.py unknown to me. Your call.

Thanks for leaving them alone rather than sweeping them into a commit.

=== KEEP GOING ===

Stats, Matchup, Odds Board, Edge Finder, Line Movement next, patterns established. Nothing above
blocks any of them. Items 1 and 2 are small dbt changes worth slotting in whenever you are next in
those models rather than as a separate pass.
```

---

## What I changed in the requirements

| Change | Where |
|---|---|
| A4 is now 17 pages; **Excel Export split out as A5** | Part 5 |
| **A6 added** — deploy-tree staleness guard as a `deployment` signal on `srv_system_health` | Part 5 |
| Note on the worktree pin's second-order effect | Part 5 |

The Airflow finding is the one I would not have caught and would not have thought to look for. A pin
that requires manual advancement is a pin that will be stale again, and the only reason this
surfaced is that Code counted models. Worth the alarm.
