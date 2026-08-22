# Claude Code prompt — build the site to the requirements

**Supersedes `cfdb_prompt_close_the_gap.md` and `cfdb_prompt_serving_databricks.md`**, both of which
were written and never sent. Everything still live in them is folded in below so you are not
juggling three documents.

Paste the fenced block whole.

---

```
Two new documents in ../claude_work/ are the build contract. Read them before anything else.

  1. ../claude_work/cfdb_site_requirements.md   — 18 pages, 208 numbered acceptance criteria.
     Part 0 is the global contract and applies to every page. Read Part 0 in full before writing
     any code; skim the page sections and return to them as you build each page.

  2. ../claude_work/cfdb_wireframe_v03.html     — open it in a browser. It is layout and intent.
     Where its pixels and the requirements text disagree, THE TEXT IS THE REQUIREMENT.

  3. ../claude_work/decision_log.md             — the four newest entries. Newest is 2026-08-20
     (later) and records this contract.

  4. ../claude_work/cfdb_publication_boundary.md — answers "can we serve X?" structurally so it
     stops being a per-case escalation.

PRECEDENCE, stated so it never costs another round-trip:
  decision_log.md  >  cfdb_site_requirements.md  >  roadmap.md  >  the wireframe.

=== TWO THINGS THAT ARE SETTLED. Do not re-open either. ===

1. postgres_only was LIFTED on 2026-08-19. Predictions build on BOTH engines.

   The reasoning, so you can apply the test yourself next time rather than escalating:
     - The licensed dataset is never uploaded to either engine. training_data.csv is not loaded
       anywhere; only model_outputs/ is. This was never a question about the pack — it is a
       question about DERIVED OUTPUT.
     - Derived output is explicitly permitted: "Use the data, notebooks, and generated outputs for
       personal analysis, academic research, or private projects."
     - The 42-column export is not a substantial portion of the dataset. NONE of the pack's 86
       training features appear in it.
     - The prohibition is on uploading PACK FILES to a notebook platform. Predictions are not pack
       files, and the workspace is single-user Free Edition.

   If the tag is still on the prediction chain, remove it, restore srv_schedule's prediction
   columns, and verify checksum parity holds across both engines.

2. PROVENANCE DECIDES, not the value. adjusted_epa from CFBD's /wepa/team/season is displayable;
   the identical column read out of the pack's training_data.csv is not. Never source a served
   model from the pack CSV even when it is easier — the pack ships 5,133 games of pre-assembled
   features and that convenience is the trap.

=== TASK 0 — the worktree pin. 20 minutes, and it is now four reports old. ===

Airflow bind-mounts the working tree, so a git checkout changes production scheduling; the live
schedule silently reverted to @daily once already. Two incidents, eight days to kickoff, and "merge
quickly" is a habit rather than a mitigation.

Bind-mount a separate git worktree pinned to main; develop in the primary tree. Verify the DAGs
still register and the cadence gate still returns the right branch afterwards.

This is the only runtime-path item in this prompt. It lands first, with verification. Everything
else is new objects or new app code and carries no date constraint per the BUILD NOW entry.

If dbt selectors/tags are not yet protecting the production refresh from a half-finished new model,
do that here too. It makes every remaining task safe to build at any time.

=== TASK 1 — RECONCILE THE CONTRACT WITH REALITY. Report, do not build. ===

I wrote the requirements from build reports and from the page-to-mart matrix. I do not have direct
visibility into the database or the deployed app, and I have marked my inferences as inferences
rather than dressing them up. Correct me before you build on them.

  a. Run `\dv serving.*` (and the Databricks equivalent) and paste the output. The requirements
     document has a serving-view inventory with a confidence column — five entries are confirmed
     from your own reports, the rest are INFERRED built because their page renders. Replace that
     column with fact.

  b. For each view that exists, list its actual columns. Where a column in the requirements exists
     under a different name, THE BUILT NAME WINS and the requirements are amended — say so, do not
     rename a live column to match a document.

  c. BUILD AN INSPECTION WORKBOOK — srv_sample.xlsx. One sheet per srv_ view, sheet name = the
     view name exactly, up to 1,000 rows sampled from each. This is the artifact that makes (a)
     and (b) reviewable rather than a wall of pasted DDL: Marc and I can open it and see the real
     grain, the real column names, the real null density and the real value shapes side by side.

     Specifics:
       - One sheet per view that EXISTS. A view that does not exist gets no sheet — the missing
         tab is the signal. List those on the index sheet instead.
       - Sheet name is the view name verbatim (srv_edge_finder, not "Edge Finder"). Excel caps
         sheet names at 31 characters; if any srv_ name exceeds that, truncate and record the full
         name on the index sheet rather than silently renaming.
       - Row 1 = column headers, exactly as the database returns them. Freeze the header row.
       - Sample deterministically and usefully, not randomly: ORDER BY the view's natural key and
         take the most recent 1,000 (most recent season/week first) so the sample reflects data we
         actually serve rather than 2003. State the ordering you used on the index sheet.
       - Include an INDEX sheet listing, per view: row count in the sample, TOTAL row count in the
         view, column count, grain as you understand it, and the ordering used. The total-versus-
         sample gap matters — a view with 900 total rows and a view with 900,000 look identical at
         a 1,000-row sample.
       - Types stay native. Numbers as numbers, timestamps as timestamps, nulls as empty cells.
         Do not stringify — half the point is seeing what the types actually are.

     This is a DIAGNOSTIC artifact for the two of us, not the Excel Export feature on page 15 and
     not a site download. It stays out of the repo. It is inside the publication boundary by
     construction — everything in serving is publishable — but it is a one-off inspection file, so
     do not wire it to anything.

  d. Report what the deployed app at <site-host> currently renders. I know the site is live;
     I do not know how much of it is real. Which pages exist, which are stubs, what does the
     current code look like against Part 0 of the requirements.

  e. Flag any acceptance criterion you believe is wrong, unbuildable, or more expensive than it
     looks. 208 criteria written without database access will contain some. I would rather hear
     that now than have you build around it.

Stop and report after Task 1 if what you find differs materially from the document. Otherwise
continue.

=== TASK 2 — THE SHARED FOUNDATION. Build Part 0 once, as components. ===

This is the highest-leverage work in the prompt. Every page consumes it; building it per page is
how a site becomes inconsistent.

  - The four-state renderer. Loading / Empty / Degraded / Error, per section, per AC-G.5 to
    AC-G.9. The Empty-versus-Degraded distinction is the one that matters most: "no games match
    your filters" and "the rankings table has not been built" mean opposite things and must never
    render alike. A Degraded section names its missing object in the UI, in code font.

  - The query helper. Enforces one relation per query, srv_ only, explicit LIMIT, st.cache_data
    keyed on the full parameter set, TTL driven by the same season-aware cadence logic the DAG uses
    rather than a duplicate rule in the app.

  - The status chip. Fixed width, glyph plus colour, five variants. Must survive greyscale
    (AC-G.21).

  - The team identity helper. Reads color_on_light / color_on_dark / color_source from dim_team.
    NEVER computes contrast in Python. Monogram fallback at identical footprint. Logos from our own
    cache, never hotlinked.

  - The query-param layer. The canonical parameter table is in requirements §0.3 — use those names
    everywhere, no per-page synonyms. Every clickable row navigates by writing query params, so a
    middle-click yields a working URL.

  - The number formatter. Fixed precision per column, right-aligned monospace, null renders as an
    em dash and is always distinguishable from zero.

  - The attribution component, sourced from the model_attribution_text column — not from page
    config. A page must not be able to render predictions without it.

Then wire nav with st.navigation / st.Page in the six wireframe groups. ALL 18 PAGES APPEAR,
including blocked ones. A blocked page renders Degraded and names its blocker. Do not hide pages
you cannot yet fill — a site that hides what it cannot do teaches the user nothing.

=== TASK 3 — the 13 pages that already have data ===

Schedule, Scores, Standings, Teams, Team page, Odds Board, Edge Finder, Model Performance,
Methodology render fully. Today, Matchup, Line Movement and Excel Export render degraded — their
schedule and market content works, their prediction or history sections render Degraded.

Build them against the per-page sections of the requirements. Two that carry more risk than the
rest:

  - Schedule (page 2). Grain is ONE ROW PER GAME. A count on the view equals the game count for the
    filtered scope, not twice it. This is the grain inversion I previously specified backwards.

  - Edge Finder (page 12) and Model Performance (page 13). Every figure on both is currently a
    2025 HELD-OUT BACKTEST, not live betting. is_out_of_sample renders as a chip on every row and
    the page carries a persistent visible statement — not a tooltip, not a footnote. A backtest hit
    rate and a realised hit rate must never render in identical styling. bucket_n renders next to
    every hit rate, always: a 17.9-point edge on n=11 is noise wearing a big number.

    Model Performance shows the seventh model as a VISIBLE ROW MARKED NOT LOADED, not as a shorter
    table. fastai_wp_predictions.csv was never written and the page states that rather than
    quietly listing six.

    Headline figures come from the view. If srv_model_performance returns numbers other than
    MAE 11.75 / SU 73.5% / ATS 51.4%, THE VIEW IS RIGHT AND THE DOCUMENT IS STALE — report the
    difference, hardcode neither.

If this prompt turns out to be more than one round, stop here and report. Tasks 0-3 are the ones
that convert the requirements into a site.

=== TASK 4 — close the four blocked pages. 13 of 18 -> 17 of 18. ===

Each is blocked by exactly one missing primary, and NONE needs a new API call:

  fct_poll_rank + dim_poll   -> Rankings          raw.raw_rankings landed (1936+)
  fct_team_season_stat       -> Stats             raw.raw_stats_season landed (1869+)
  dim_field_metadata         -> Data Dictionary   dbt schema.yml + persist_docs
  fct_dq_test_result         -> System Overview   dbt run_results.json, already written every run

For dim_field_metadata: ../claude_work/cfdb_data_dictionary.xlsx is the generated upstream input.
CFBD's OpenAPI spec documents 74/74 endpoints and 289/289 parameters but only 4 of 1,017 FIELDS, so
field descriptions are ours to author — 151 of them inside Phase 1. Descriptions live in dbt
schema.yml with persist_docs so the site page and the Excel sheet cannot drift. Carry a per-field
status; UNDOCUMENTED is an honest value and better than a plausible guess, and the page renders it
as a first-class value rather than hiding it.

For srv_team_stats: emit all four stat_scope x stat_basis combinations AS ROWS. The toggles filter;
they do not compute.

=== TASK 5 — two prediction fixes ===

5a. MOVE home_cover_edge from the serving view into fct_prediction.

Your derivation is correct — spread - predicted_margin is the contract's own formula, so applying
it is not inventing a metric, and is_edge_from_export is the right provenance guard. Keep both.

But it is a per-prediction measure. Leaving it only in srv_edge_finder forces srv_model_performance
and the Excel export to re-derive it independently — three copies of one formula, which is how
definitions drift silently. Derive once in marts, consume everywhere.

5b. DE-VIG METHOD DECIDED: multiplicative normalisation.

    implied_home = (1/home_decimal) / ((1/home_decimal) + (1/away_decimal))

You were right to leave market_implied_home_win_probability blank rather than guess — it is a
modelling call. The call: multiplicative, because it is the standard two-way de-vig, it is one
line, and its assumption (vig is proportional to implied probability) can be stated plainly on the
Methodology page. Shin's and the power methods correct favourite-longshot bias better, but the gain
on two-way markets is small and the explanation is long. For a project whose differentiator is
honest measurement, explainability outranks marginal accuracy.

Two requirements that keep it reversible:
  - Store a devig_method column beside the probability, so the choice is auditable and a second
    method can be computed later and compared without rewriting history.
  - Raw moneylines stay untouched in fct_betting_line. De-vig is derived, never destructive.

That unblocks home_win_probability_edge, which completes the Edge Finder contract. Document the
assumption in dim_field_metadata when Task 4 lands it.

=== TASK 6 — the two missing serving views ===

srv_matchup and srv_today_edges. Both pages already render degraded, so this is enrichment — but it
is cheap now that fct_prediction carries real data, and it takes two pages from degraded to full.

srv_matchup is deliberately the widest view in the model. It is the page where a user decides
whether to bet, so it carries both teams' identity and ratings, the market with its capture
timestamp, the model with its interval, weather, venue, travel, rest and series history. The full
column list is in requirements page 10. Build it wide — a page issuing one query against a wide
view is the design, not a compromise.

line_captured_at is not optional on any view carrying a line. A line without a capture time is not
usable for edge, and the Formatted-Spread-versus-Spread divergence in the historical workbooks is
exactly what happens without it.

=== EXPLICITLY NOT NOW ===

  - Players (page 9). Four tables and some new ingestion, and it is the only blocked page whose raw
    data is not already on disk. It goes after Task 6 and takes the site to 18 of 18.
  - fct_team_week_rating. The largest enrichment in the backlog and primary on ZERO pages. It waits
    until after Players.
  - Live in-game scoring, bet logging, leaderboards, sub-768px layouts. See requirements
    Appendix B — these are decisions, not oversights.

=== CONSTRAINTS ===

  - Task 0 is runtime-path: land it first, with verification. Everything else is new objects or new
    app code and carries no date constraint.
  - Show dbt build output, row counts, and the parity check. Do not report success without them.
  - For app work, show the page rendering in each of its four states — not just the happy path. The
    states are most of what the requirements are about.
  - Anything unresolved goes in DECISIONS NEEDED rather than a guess. A narrow implementation that
    is wrong is cheap to widen; a wide one that is wrong has to be found first.

=== WHAT TO REPORT BACK ===

  1. Task 1's reconciliation in full — the real view inventory, the real column names, the real
     state of the deployed app, and every acceptance criterion you think is wrong. Attach
     srv_sample.xlsx; it is the fastest way for us to see what actually exists.
  2. Which acceptance criteria now pass, by number. AC-G.1 through AC-G.52 first, then per page.
  3. What you did not get to, and why.
```

---

## Why the prompt is ordered this way

**Task 1 exists because I do not have database access and said so in the requirements.** Five of the
eighteen serving-view statuses are confirmed from build reports; the rest are inferred from "the page
renders". Two hundred and eight acceptance criteria written without seeing a schema will contain
some that are wrong, and the cheapest moment to find that is before any of them are built against.
The instruction that the built name wins over the document name is the specific guard against
repeating the `fct_game` / `fct_game_team` inversion — that error came from writing a spec off object
names instead of off the database.

**`srv_sample.xlsx` is the part of Task 1 I expect to pay for itself fastest.** A pasted column list
tells you names; a thousand real rows per view tells you grain, null density, sign conventions and
value shapes at a glance — which is where the errors in my document will actually be. The index
sheet carries total row counts alongside sample counts, because a view with 900 rows and one with
900,000 are indistinguishable at a 1,000-row sample and that difference changes what a page can do.
It is a diagnostic file, explicitly not the page-15 Excel Export feature, and it stays out of the
repo.

**Task 2 before Task 3 is the one ordering choice I would defend hardest.** The global contract is
about two thirds of the value in the requirements, and it is the part that decays fastest if built
per page. Four-state handling, the chip, team identity and the query-param layer implemented six
different ways across thirteen pages is a rewrite, not a site.

**Task 4 comes after the app work, which inverts the previous prompt.** That is deliberate and worth
flagging in case you disagree. The four tables are cheap, well-understood and unchanged since the
last three prompts — they will land whenever they are scheduled. The app has been blocked on not
having requirements, and now is not. If you would rather see 17 of 18 pages have data before any
Streamlit work, swap Tasks 3 and 4 — the prompt survives the swap intact.

**The stop point is explicit.** Seven tasks is more than one round, and a round that half-finishes
six things is worse than one that finishes three. Tasks 0–3 are the set that turns the requirements
into a running site.
