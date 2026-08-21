# Claude Code prompt — Week 0 readiness, then breadth

Paste the fenced block whole. Marc's direction: **calibration is parked until Week 5.** Priority is
the breadth and accuracy of what the site serves, and how useful it is to a person on 27 August.

---

```
DIRECTION CHANGE FROM MARC, and it is a simplification: model tuning is a Week 5+ problem. Do not
spend time on calibration, recalibration or the decile curve now. Park it. Keep the segment data you
built — it is correct and it will be waiting.

What matters now: the breadth and accuracy of the serving layer, and whether the site is genuinely
useful to someone on Thursday 27 August.

That reframes the order. Two things go ahead of finishing pages.

=== TASK 1 — THE POST-GAME PATH HAS NEVER RENDERED REAL DATA ===

This is the one I would want to find before Thursday rather than during it.

Every page you have built was verified against 2026 fixtures, and every 2026 fixture has
is_completed = false. Look at what that means across srv_sample:

  srv_scoreboard      home_points, away_points, winner, actual_margin, is_upset,
                      excitement_index, attendance    ALL NULL, every sampled row
  srv_schedule        home_points, away_points                        ALL NULL
  srv_team_game_log   points_for, points_against, result, margin, first_downs,
                      total_yards, rushing_yards, passing_yards, turnovers,
                      third_down_conversions, possession_seconds      ALL NULL
  srv_matchup         home_points, away_points, actual_margin         ALL NULL

So the PRE-game render path is proven and the POST-game render path has never executed against real
values anywhere on the site. Scores, the Schedule post-game card state, the Team page game log,
Matchup's result block and Standings' records are all first-run on Thursday night, live, in front of
whoever is watching.

Nothing about that is your error — the sample is 2026 because 2026 is what is upcoming. But it means
the half of the site that matters most on game day is untested, and the fix is cheap because THE
DATA IS ALREADY THERE.

REHEARSE IT: point every page at a completed 2025 week and walk it.

  - Scores: winner shading, cover_result chips, push distinct from pending, is_upset, actual_margin
    sign (a home win must show a NEGATIVE actual_margin — this is the one that silently inverts
    everything downstream)
  - Schedule: the pre-game to post-game card transition on the same row
  - Team page game log: every box-score column, and a road underdog game specifically, because that
    is where an orientation bug shows
  - Matchup: the result block and prediction-vs-outcome side by side
  - Standings: records, streaks, last-5, ATS records with real graded games

Report what breaks. My expectation is that something will — a null-safe formatter that has only ever
seen nulls, a chip with no post-game branch, a column that was never exercised. Better Wednesday
than Thursday.

Then keep a completed-2025-week fixture in CI permanently, so the post-game path is exercised on
every build rather than four times a season.

=== TASK 2 — ONE OPERATIONAL QUESTION I CANNOT ANSWER FROM HERE ===

As of the 2026-08-17 audit the DAG schedule was:

  cfbd_lines_snapshot    4-hourly in season (cadence gate landed)
  cfbd_results_refresh   Sunday 12:00 UTC
  cfbd_pregame_refresh   Tuesday 12:00 UTC

If results still refresh only on Sunday, then the first FCS games on Thursday 27 August and the first
FBS games on Saturday 29 August do not appear as final until SUNDAY 30 AUGUST. The Scores page —
which is the single most-visited surface on any sports site during a game week — would be up to three
days stale for the whole opening weekend.

I do not know whether that has already changed. Tell me what the cadence actually is now. If it is
still weekly, this is more urgent than any remaining page, because a Scores page showing Thursday's
games as "scheduled" on Saturday morning is worse than not having the page.

If it needs changing, the same season-aware gate that drives the lines cadence is the pattern —
frequent during game windows, quiet otherwise, no seasonal schedule edits.

=== TASK 3 — THE GAME-DAY PAGES, IN THIS ORDER ===

  1. Matchup       the decision surface, the widest view, and the only page that answers
                   "tell me about THIS game." Also the click target for every row on the site
  2. Odds Board    market data needs no model, so it is fully useful from day one
  3. Line Movement same
  4. Stats         breadth, and the raw-only scope is already decided
  5. Data Dictionary + Methodology   lower urgency for a Saturday user, high for the portfolio

Matchup first because it is where every other page points. A site where rows are clickable and the
destination is thin is worse than one where they are not clickable at all.

=== TASK 4 — B1, AND IT IS NOW A BREADTH ITEM RATHER THAN A DE-PARTIALER ===

fct_team_week_rating. Marc's framing makes this MORE important, not less: it is the largest single
addition of genuinely informative content on the site, and it is what a user actually wants in weeks
1-4 when there is no model to look at. SP+, Elo, SRS, adjusted EPA are the numbers that make a team
page worth reading.

From CFBD's landed ratings endpoints — /ratings/sp, /ratings/elo, /ratings/srs, and the /wepa and
/ppa families. NEVER from the pack's training_data.csv, which ships 5,133 games of exactly these
features pre-assembled. This is the one model where the provenance trap will be genuinely tempting.

=== WHAT ELSE ADDS BREADTH CHEAPLY, if there is room ===

These make weeks 1-4 substantially more interesting and none needs a model. Raw is landed for all of
them:

  fct_game_weather        Matchup. 5 files landed
  venue join key          fct_game carries a venue NAME, not an id -- this blocks rest, travel and
                          elevation, which are three of the most interesting context columns on
                          Matchup and cost one key to unlock
  network                 raw/games_media landed, unmodelled. Small staging model. Every schedule
                          row on ESPN carries it
  excitement_index        112,272 raw games carry it, unmodelled. It is the single best
                          "was this game worth watching" signal and it is sitting in raw

The venue key is the best value of those four -- one join key unlocks three columns that make
Matchup feel like a real preview rather than a table.

=== CONSTRAINTS UNCHANGED ===

  - Serving only, one relation per query, no metric maths in the app.
  - Empty vs Degraded stays the distinction that matters.
  - Show row counts before and after any widening, and parity across both engines.
  - Anything unresolved goes in DECISIONS NEEDED rather than a guess.
```

---

## Why Task 1 goes first

Nine pages render, and the half of them that matters on a Saturday has never run against a completed
game. That is not a criticism of the build order — 2026 is legitimately what the sample contained —
but it means the opening weekend is also the first integration test of the post-game path, and the
`actual_margin` sign convention is in that path.

It has been verified 3,402/3,402 *in the data*. It has never been verified *on screen*. A display
layer that flips a sign is a different bug from a model that does, and only one of them has been
ruled out.

The rehearsal costs an afternoon and the data is already sitting in the warehouse.
