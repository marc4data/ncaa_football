# Claude Code — next prompt (revised: BUILD NOW)

Supersedes the earlier "spec now, build after Sep 7" version. Paste the fenced block whole.

---

```
Read these first, in this order. They have changed since your last session:
  1. ../claude_work/decision_log.md — FOUR new entries dated 2026-08-18 at the top. The newest,
     "BUILD NOW", changes the sequencing and refines the freeze rule. They outrank anything you
     remember.
  2. ../claude_work/cfdb_model_reconciliation.md — your own audit. Still authoritative on what exists.
  3. ../claude_work/cfdb_team_identity_spec.md — colour/logo handling for dim_team.

TWO CORRECTIONS TO YOUR LAST MESSAGE:

1. "Nothing to build until after Sep 7 regardless" is not the rule, and Cowork's earlier prompt
   wrongly agreed with you. The freeze protects the RUNTIME PATH. New objects that nothing reads
   are not on it. The strangler migration exists precisely so new construction is invisible to the
   running system — building dim_conference or fct_game touches neither mart_team_schedule, nor
   the publish job, nor the site. The refined rule is in the BUILD NOW entry:
     - New objects nothing reads .................. no freeze, build any time
     - Cutover of a page to a new view ............ gated on the PARITY TEST passing, not a date
     - Runtime changes with no parity proof ....... still date-gated (before 08-27 / after 09-07)
     - Lines cadence gate ......................... exception, must land by 2026-08-20

2. The deadline that binds is 2026-08-20, not 2026-08-27. Week 0 is resolved: first games of the
   season are Thursday 2026-08-27 (FCS-only), first FBS slate 2026-08-29. The 7-day lead anchors
   on 08-27, so the lines window opens 2026-08-20 and closes 2027-01-27 (CFP championship is Mon
   2027-01-25 at Allegiant Stadium; +2 days for the UTC overrun on a 7:30pm ET kickoff).

THE TARGET: the full Phase 1 model standing and validated against live Week 0 data
(2026-08-27 → 08-30). Not a spec parked for September. A model that cannot handle Week 0 is far
better discovered against ~20 games than against a 60-game Saturday.

=== PART 0 — GATE. Before anything else. ===

Report the current state of cfbd_lines_snapshot: its schedule right now, whether the season-aware
short-circuit is implemented, whether the window config is externalised, whether it loads or still
only fetches, and recent run history.

IF the cadence gate is NOT fully landed: STOP. That is the whole session. Implement it per the
2026-08-18 decision-log entry — permanent `0 */4 * * *` UTC schedule with a short-circuit letting
only the 00:00 run through outside the window; window 2026-08-20 → 2027-01-27; the decision a pure
unit-testable function; LOG the branch on every run including skips; load as a task SEPARATE from
fetch so a load failure never blocks the next fetch. Show tests passing and correct branches for
2026-08-19, 2026-08-20T00:00Z and 2026-08-20T04:00Z. Then stop and tell me.

IF it IS landed: say so with evidence and continue.

=== PART 1 — Spec, fast. Then build. Same arc, not two sessions. ===

Write ../claude_work/cfdb_phase1_model_spec.md first, but treat it as a working document that
unblocks the build rather than a deliverable parked for review. I will review it as it lands.
Start building as soon as a given object's section is settled — do not wait for the whole spec.

For each object: name, layer, target schema, grain stated as its uniqueness key, columns with
types, surrogate key strategy, source model(s)/endpoint, materialization, and the tests that prove
the grain.

BUILD ORDER — dependencies first, then the things Week 0 will exercise hardest:

  1. `serving` schema created in both engines; publish job and CI layering guard extended to know
     about it. Do NOT move search_path yet — that is a cutover step.
  2. dims:   dim_season · dim_week · dim_conference · dim_venue · dim_provider
  3. dim_team — promote stg_teams to marts with a surrogate key. SEASON-SCOPED, NOT SCD2. Add
     color, alternate_color, logos (in raw, never selected) plus the contrast-safe derived columns
     from cfdb_team_identity_spec.md: color_on_light, color_on_dark, color_source. Computed in dbt,
     not the app.
  4. fct_game — promote stg_games (grain already correct) to a mart with keys.
  5. fct_game_team — normalized in marts, extended with /games/teams box scores.
  6. fct_betting_line — grain game x provider x snapshot_ts, append-only. Keep BOTH spread and
     formatted_spread as separate columns; they disagree historically and neither is known
     authoritative. Do not reconcile them.
  7. fct_team_record — keeps deriving from stg_games. Add tiebreak_rank (CFBD has no standings
     endpoint, so ordering is our logic). Add a reconciliation TEST against /records, which is
     landed and unused.
  8. srv_ views + PARITY TESTS: srv_schedule · srv_scoreboard · srv_standings · srv_teams_index ·
     srv_team_game_log · srv_line_movement

NON-NEGOTIABLES:
  - mart_team_schedule, mart_team_season_record and mart_data_freshness are NOT renamed, NOT
    dropped and NOT repointed in this work. They keep serving the live site throughout Week 0.
    That is the entire point of building alongside them.
  - THE PARITY TEST IS THE CUTOVER GATE and I care about it more than the views it protects. For
    each srv_ view replacing a live mart, build a dbt test proving row-for-row identity with that
    mart. Specify concretely: what is compared, how nulls and column ordering are handled, what a
    failure reports. It is allowed to say "not yet" — that is it working.
  - dim_provider: DraftKings canonical, "Draft Kings" mapped in staging. Preserve provider_raw AND
    add provider_key. A test must FAIL on an unmapped provider_raw so a new sportsbook surfaces
    loudly instead of quietly becoming a dimension member.
  - dim_week: record the /calendar 2002 floor as a documented constraint with a test. season_type
    is part of the key — PostSeason Week 1 is not Regular Season Week 1.
  - fct_endpoint_freshness is the rename target for mart_data_freshness. It is NOT fct_pipeline_run
    — that is a different, unbuilt table. Note the target; do not rename yet.
  - Every model gets schema.yml descriptions on every column, a uniqueness test on its declared
    grain, and not_null on its keys. All 6 existing models already meet this; nothing new should
    lower the bar.
  - Both engines. Postgres and Databricks parity is checksum-verified today; it stays that way.

WEEK 0 READINESS — call this out explicitly when you report:
  Which of these objects will actually be exercised by the 2026-08-27 → 08-30 slate, what you
  expect to break, and what you will be watching. Week 0 is FCS-heavy on Thu/Fri, which makes it a
  real test of the non-FBS opponent stub rule (is_fbs = false, no deep stats, records and schedules
  must still reconcile).

CONSTRAINTS:
  - Do not guess. Anything unresolved goes in a DECISIONS NEEDED section — that section was the
    most useful part of your reconciliation report.
  - If a decision-log entry contradicts what you find in the repo, stop and say so rather than
    working around it.
  - If any Phase 1 object looks like ceremony rather than load-bearing, say so. Three layers over
    ~33 warehouse tables plus 18 serving views is a lot of surface for one person against a stated
    low-upkeep constraint. I would rather cut one now than maintain it for a year.
  - Show dbt build output and row counts. Do not report success without them.
```

---

## What changed and why

**The sequencing error was mine.** I had you spec now and build after Sep 7, which contradicts the
strangler migration I recommended in the same breath. The strangler exists so new construction is
invisible to the running system — so a runtime-path freeze doesn't apply to it. Building
`dim_conference` touches nothing the site reads.

**The freeze rule is now an evidence rule where evidence exists.** Cutover is gated on the parity
test passing rather than on a date, because a passing proof that the swap is a no-op is stronger
than a calendar. Keeping a date rule on top of that would be paying for the safety mechanism twice.
Date-gating survives only for runtime changes that have no parity proof available — schedule
changes, schema moves, `search_path`, publish-job rework.

**Week 0 is now the target, not an obstacle.** ~20 games, FCS-heavy, real data. It's the cheapest
possible live test of the non-FBS opponent stub rule, which is the part of the model most likely to
be wrong and least likely to be caught by synthetic checks.

**One thing I did not change:** the live site keeps reading `mart_*` through Week 0. "Build now"
does not mean "cut over during the opening weekend," and the prompt says so twice.
