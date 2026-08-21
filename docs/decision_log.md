# cfdb Decision Log

Decisions made in Cowork (strategy/governance surface). Claude Code implements within these. Newest first.

## 2026-08-23 (later) — The uniqueness sweep found a defect in a model one hour old

268/268 dbt · 233/233 production · 42/42 page queries · 211 pytest. Published, deployed, CI green.

### Sweep 2 paid for itself immediately, in the newest code in the repo

**Eleven of twelve facts clean. The twelfth was `fct_team_rating`, shipped an hour earlier** — three
duplicate natural keys.

CFBD's `/ratings/srs` returns some schools **twice**: once with a conference, once with
`conference: null`, **carrying an identical rating**. Charlotte 2024 and 2025, Troy 2024.

**The predicted signature exactly:** the rating is the same on both copies, so **no average moved and
no value looked wrong**. What moved was every count and **every percentile denominator** — SRS
percentiles computed over **266 rows for 265 teams**. Nobody reviews a denominator.

**The lesson worth keeping: recently written is the least-tested code**, and the instinct runs the
other way because it is fresh in mind. A sweep that finds nothing in eleven mature models and one
defect in the hour-old one is close to the ideal outcome — it proves the sweep is load-bearing rather
than ceremonial.

`assert_facts_are_unique_on_their_natural_key` now covers all twelve, naming the business key.
Verified by re-injecting the exact duplicate it found; the CI fixture carries a duplicated SRS row so
the dedup runs every build. **Fifth time a failure case has been kept alive rather than deleted.**

**Open question raised to Claude Code:** the duplicate rows differ only in completeness, so the dedup
has a **precedence** question in it. If it picks arbitrarily, some fraction of the time it keeps the
null-conference copy and Charlotte silently loses its conference. The rule should be explicit —
**prefer the more complete record**, and assert the copies agree on everything else.

Same *shape* as `/teams` versus `/games`: CFBD emitting a **partial record alongside a complete one
for the same entity**. Distinct from Sweep 1's aggregate-rows class, and now detected at build time
by the uniqueness test — so this is a precedence question, not a detection one.

### Sweep 1: `nationalAverages` is the only one

All 65 raw tables, every identity field at any depth. Already excluded.

**The instructive part is the first pass.** The heuristic matched the substring "All" and flagged
**Allen, Allison, Allar** — real players. Claude Code's rule:

> **"A check that flags real data teaches you to skim its output."**

Narrowed to a **lowercase-initial identifier**, since every real school and player is a proper noun —
distinguishing on what actually separates the classes rather than on a substring that happens to
correlate.

### That rule condemns a check Cowork designed

**AC-16.6** requires every `srv_` column to carry a description, set to `warn` until coverage clears a
threshold. **Coverage is 30.5%, so it emits ~665 warnings on every build**, none of which will change
tomorrow. By Claude Code's own rule that is the noisiest thing in the project and it actively trains
both sides to scroll past build output. **A wallpaper generator.**

**Fix, keeping the intent: aggregate to ONE warning per build** —
*"documentation coverage 30.5% (292/957), target 60%, 665 columns undocumented"*. **One line that
moves is readable; 665 lines that do not move are wallpaper.** Same information, behaving like a
metric rather than a fault list. Escalate to `error` at the threshold as before.

**Generalised:** ask it of every check that can emit more than a handful of rows. The test is not *"is
it correct"* — all of ours are. The test is **"would a human read all of its output."** If no, it
needs aggregating, and **a check nobody reads is a check that is not running.**

### `rating_population` — the denominator becomes a column

`rating_population` carries the `n` each percentile was computed against, per system. The page renders
**"86% of 136"**, not "86%".

The reason is load-bearing: **the denominator moves.** SP+ covers 139 teams today and Elo covers none;
when Elo appears mid-season it may cover a different set again. A percentile over a shifting
population with no `n` attached **silently changes meaning between August and October.**

**This is the first place AC-G.33 is a column rather than a hope, and it should spread** — team-stats
percentiles have the same exposure, with a qualifying population that moves with the through-week
filter.

### On the naming error

Claude Code's note that `fct_team_week_rating` was *"a reasonable guess from a true premise"* is
generous but the credit runs the other way: **the instruction to check the grain was a scar, not an
insight** — the product of having been wrong four times by not checking, with no specific suspicion
about ratings. The fetch-log check was Claude Code's.

### Next

Skipped-test reporting → `sync_freshness` → Standings carries the rating columns.

**Marc has `cfdb_site_feedback.md` and is walking the site.** Expect experience-level feedback rather
than data-level — the one class neither Cowork nor Claude Code can generate, because everything
verified so far is a query, a count or a test, and none of it is the experience.

## 2026-08-23 — `fct_team_week_rating` could not be built as named; two payload defects that generalise

267/267 dbt · 232/232 production · 42/42 page queries · 211 pytest. Published, deployed.

### The name asserted a grain no source could supply — Cowork's error

| Endpoint | Accepts `week`? | **Actually fetched as** |
|---|---|---|
| `/ratings/elo` | **yes** | **season only** |
| `/ratings/sp` | no | season |
| `/ratings/srs` | no | season |
| `/ratings/fpi` | no | season |
| `/ppa/teams` | no | season |

Cowork's guesses were half right — Elo is weekly-*capable*, PPA is not. **The decisive fact is that
Elo has only ever been fetched with a year.** `fct_team_week_rating` would have been **one real
column and four fabricated ones.**

`fct_team_week_rating` went into the requirements a week ago because "ratings change weekly" sounded
obviously true, and nothing checked whether anything was fetched that way. **Weekly-capable versus
weekly-fetched is exactly the distinction assumption misses.**

**Built as `fct_team_rating` with `rating_scope` carrying `'season'`**, so a weekly Elo backfill is
**additive rather than a redefinition**. Trends stays Degraded and now names the real blocker — **a
fetch change, not a model.**

### Every 2026 rating that exists is a forecast

**SP+ 139 · FPI 138 · Elo 0 · SRS 0 · PPA 0.**

The only ratings that exist before a game is played are the two that are **projections**. Elo, SRS
and PPA are results-derived and have nothing to compute from. So **`is_projection`** — derived from
whether the team has a completed game, **asking the data rather than keeping a list of which systems
are predictive.** Fourth instance of that habit.

Alabama 2026 reads **SP+ 17.6 (13th, 91st percentile)** and **FPI 20.1 (8th)**, both labelled
forecasts. **Real content on the Team page from day one.**

**The flag has a second job.** The ratings block **changes character mid-season**: in week 0
everything on it is a forecast; around week 5 SP+ and FPI become results-informed *and* Elo, SRS and
PPA appear for the first time. A user looking at Alabama in August and again in October sees a
different set of numbers meaning different things. `is_projection` is what makes that legible rather
than confusing — it explains why a number moved a lot and why new rows appeared. **Render it as a
visible state, not a footnote.**

**Watch when the others arrive:** percentile denominators. SP+ percentiles are over 139 teams today;
Elo may cover a different set. A percentile over a shifting denominator is AC-G.33 again — **the rank
carries the `n` it was computed against, per rating system**, not a site-wide team count.

### Two payload defects, both classes rather than incidents

**1 — an aggregate row inside a member payload.** SP+ publishes a `nationalAverages` row. In a team
fact it would have landed on the Teams index, earned a team page, and **sat in the percentile
denominator — "shifting every team's standing by an amount nobody would trace back."** Silent,
plausible, and it contaminates a *denominator* rather than a value, so every number moves a little
and none looks wrong. The CI fixture carries the poison row so the **exclusion** runs on every build,
not just the fix.

**Sweep proposed:** check the other 64 raw tables for rows whose identity field is not a team, a game
or a player. Any endpoint that might embed a total, an average or an "all" bucket.

**2 — six copies of the same fetch.** 834 SP+ rows for 138 teams. **"Six copies average out to a
plausible number while every count is six times too big."**

**Why this is the sharpest finding of the week:** a duplicate fanout **passes every mean-based check
and fails only count-based ones.** Averages, percentiles and rankings all come out approximately
right; nobody looks at counts. It survives review, survives eyeballing, and surfaces as a subtly
wrong rank months later.

**And the exposure is structural, not incidental — the revisionist cadence means the raw layer holds
multiple responses per entity BY DESIGN.** Lines re-fetch 4-hourly; rankings, results and pregame
weekly. **Every fact built on a re-fetched endpoint has this exposure, and only the ones checked are
proven clean.**

**Sweep proposed: a uniqueness test on the NATURAL key of every fact, not the surrogate.** A
surrogate built by hashing is unique by construction and proves nothing — if the hash includes a
fetch timestamp, six copies produce six distinct `sk`s and the table looks fine. The test must name
the business key: `fct_game` on `game_id` · `fct_game_team` on `(game_id, team_id)` ·
`fct_team_record` on `(season, team_id)` · `fct_team_season_stat` on `(season, team_id, stat_name)` ·
`fct_poll_rank` on `(season, season_type, week, poll, team_id)` · `fct_betting_line` on
`(game_id, provider_key, snapshot_ts)` · `fct_team_rating` on `(season, team_id, rating_system)` ·
`fct_prediction` on `(game_id, model_name, model_version)`.

Most will pass. **The point is that "we checked" replaces "it looked fine."**

### Cowork's rules landed

The selector guard's docstring now states **why it cannot be a dbt test** — a dbt test runs only for
selected models, so it narrows with the thing it checks. Both parity gates carry the
which-side-is-right amendment.

### Next

Skipped-test reporting → `sync_freshness` signal → Standings carries the rating columns. Then the two
sweeps above.

**And one for Marc, not Claude Code: nobody has walked the site as a USER.** Every check so far has
been a page query, a row count or a test — all correct, none of them the experience. Six days out, an
hour of clicking through on the device he would actually use will surface what no assertion can: a
filter that resets, a link that goes somewhere odd, a table needing horizontal scroll on a laptop,
copy that reads wrong.

## 2026-08-22 (evening) — A guard scoped by the thing it guards; B1 grain check; Standings shipped

264/264 dbt · 229/229 selector · 211 pytest · flake8 clean. Published via the restricted key,
deployed.

### THE FOURTH INSTANCE — and it has a shape the other three did not

`cfbd_midweek_results` ran at 12:06 UTC today, **succeeded**, and reverted the
`mart_team_season_record` fix — putting **7,482 null team names back**. The pinned deploy tree
predates the branch, so it rebuilt the mart from its defective definition.

**The detail that makes it sharper than the others:** under the old six-model selector, the parity
gate **is not selected**. `srv_standings` is not in the selection, so a singular test referencing it
**does not run**. Claude Code's sentence is the finding — *"the divergence was created by a run that
structurally could not detect it."*

**THE RULE: a guard must not be scoped by the mechanism it checks.**

A dbt test runs only for **selected** models. Narrowing the selector narrowed the guard, silently, in
the same motion — and **nothing in a green run distinguishes "passed" from "was never asked."**

- A parity test selected by the production selector cannot protect against a bad production selector.
- A freshness check that only runs when the pipeline runs cannot detect a pipeline that stopped.
- A test living inside the thing it tests inherits that thing's failure modes — **including "did not
  happen."**

`ci/check_production_selector.py` is already the correct answer and predates this firing: it runs in
**CI, against the manifest, outside the dbt selection.** That is what makes it a guard rather than a
participant, and the reason it *cannot* be a dbt test belongs in its docstring — because that is
exactly what someone will later try to turn it into.

**Extension proposed:** have the run summary report tests **SKIPPED** as well as passed and failed. A
green summary that silently omits what it never asked is the same ambiguity as the missing conference
segment and the `->> '0'` null.

**Four instances, one sentence: every one checked that something RAN and never that it PRODUCED
anything — or today, never that it was even ASKED.** Site was unaffected; the old selector never
touched `srv_*`. Stops when #21 merges and the pin advances.

### Both sides correct beats expected divergence

Claude Code fixed `mart_team_season_record` in step rather than recording a divergence. **Better than
the amendment Cowork wrote.** An expected divergence is a permanent explanation someone has to keep
re-reading; two correct sides need no explanation. **Record divergences only when the old side is
genuinely being retired and fixing it would be wasted work.**

### Standings shipped — and two things worth keeping

**ATS moved to `fct_team_record`** so Standings and the Team page share one definition. **Proved
faithful before repointing:** 22,993 team-seasons, `ats_record_display` identical on every one, with
**34 differences all `0-0` → NULL**.

> *"A team that was an underdog in all eleven games was never a favourite, and `0-0` claims a record
> it never had."*

That is AC-G.32's not-applicable state at a finer grain, found where neither side was looking. **The
pattern for any future definition move: prove identity first, explain every difference, then
repoint.**

**Division was the predicted trap and had a case Cowork did not specify.** 14 of 136 FBS teams have
one; absence renders as **nothing at all** — no header, no state. And a conference can have divisions
*and* teams outside them, which is what mid-season realignment looks like — those render too rather
than being dropped. AC-5.2 said "group by division where a conference has them" and did not cover the
mixed case.

Splits exclude neutral-site games from both home and away, with `neutral_games` carried so the three
reconcile.

Cowork's staleness caveat earned its place — `team_slug` / `team_display` had already shipped.

### Scores DAG — "ask the data, don't encode the rule" is now three

Every two hours, **gated on whether a game actually kicked off recently** — asking the schedule
rather than encoding which days football is played. Two requests, not 31. Narrow selection: 27
models, not 52. **Publishes**, because a fresh `fct_game` that never reaches the droplet has not
helped anyone.

| Instance | Replaces |
|---|---|
| `dim_season.is_current` | a hardcoded default season |
| `training_week_floor = 5` | a hardcoded "predictions begin Week 5" |
| "did a game kick off?" | a hardcoded list of football days |

**Default question for any new rule: is this knowable from data we already have?**

Enumerating the branches as a table found a gap between them — the first version skipped when the
schedule was unreadable, contradicting its own docstring. **It now fails open in season: "two wasted
requests cost less than a stale scoreboard when Postgres blips on a Saturday."** Choosing the fail
direction by stated cost asymmetry, with the reasoning in the docstring so nobody "fixes" it later.

### Databricks sync failing — noted, not chased, but parity claims decay

`cfbd_databricks_sync` exceeds a 900s retry budget on the free-tier warehouse. Analytics tier, not
user-facing. **Right call not to chase it six days out.**

**But dual-engine checksum parity is one of the better engineering stories here, and a stale parity
proof reads exactly like a live one.** Cheap fix, no chasing: add a **`sync_freshness`** signal to
`srv_system_health` alongside the other five, so "we have dual-engine parity" becomes a statement
with a timestamp on it. Whether to repair the free-tier sync — or whether dual-engine is still worth
it — is a post-Week-0 decision for Marc.

### B1 — check the grain before committing to it

`fct_team_week_rating`'s name asserts week grain. **Verify that of the sources first**, from the
landed raw files:

| Endpoint | Believed | |
|---|---|---|
| `/ratings/elo` | takes a week parameter — **genuinely weekly** | |
| `/ratings/sp` | year + team — likely season-level | uncertain |
| `/ratings/srs` | year + team — likely season-level | uncertain |
| `/ppa/teams` | year + week — likely weekly | uncertain |

**It matters because the Team page Trends tab depends on it.** If only Elo and PPA carry weekly
history, Trends is an Elo/PPA time series with SP+ and SRS as season markers, not a four-line chart.

**If the sources are mixed, carry a `rating_scope` column (`season` | `week`) rather than
forward-filling a season value across weeks.** A season-final SP+ repeated across fourteen weeks is a
**fabricated time series** — same class as `ats_record_display` showing `0-0-0`, and it would look
completely convincing.

Otherwise B1 is settled: CFBD's landed ratings endpoints, never the pack's `training_data.csv`. It
de-partials Team page (Ratings, Trends), Matchup and team profile percentiles — and in weeks 1–4 with
no model to show, it is the most informative content the site carries.

## 2026-08-22 (later) — The premise check changed the design; the parity gate needed amending

264/264 dbt · 229/229 production selector · 41/41 page queries · 199 pytest · flake8 clean. **Publish
is now automated end-to-end** — verified from inside the Airflow image, 321 MB, 17 tables, every count
agreeing.

### Two Cowork errors in one control, and the second was the expensive one

**`sql <text>` in a forced-command allowlist.** Cowork sketched a forced command and then put an
arbitrary-SQL verb inside it — which hands back exactly the execution the forced command exists to
remove. **A padlock with the key taped to it.** Claude Code replaced it with five fixed verbs and
validated identifiers; `count serving; drop schema serving cascade; --` is refused at identifier
validation.

**`cfdb_publish` in the docker group would have been theatre.** Cowork recommended "non-root user"
without knowing the Docker socket was in the path. **Docker group membership *is* root** —
`docker run -v /:/host` and you own the machine. Followed literally, the recommendation would have
produced a control that *looked* like a privilege reduction and was materially identical to what it
replaced.

**That is worse than no control, because it spends the credibility of the real ones.** Same family as
the monogram fallback firing 100% of the time: something that appears to be working precisely because
it never does anything.

**The actual reduction was removing Docker from the path.** Postgres bound to `127.0.0.1:5433` —
loopback, not routable, UFW still 22/tcp only — and `cfdb_publish` (no docker group) reaching it with
`psql`. Blast radius is now what it can do to the serving database, which is what publishing *is*.
The forced command becomes a genuine second layer rather than the only one.

**Five attack attempts, all refused:** open a shell · `cat /opt/cfdb/.env` · `docker ps` · arbitrary
SQL · SQL injection through an identifier. Fourth time a control has been proven by trying to break
it. **Standing practice now, for every control, not only security ones.**

Cloudflare Tunnel does **not** route SSH — token-based tunnel, ingress in the dashboard, site
hostname only. Recorded, not built.

### DECIDED: the parity gate is amended, because it can fail for the right reason

The cutover gate was specified as *"row-for-row identical to the mart it replaces."* **That breaks
the moment the new side gets better** — and it did. `mart_team_season_record.school` inherited the
`dim_team` null-identity defect, `srv_standings` was fixed, and the gate failed on **14,964 rows
because the serving view became more correct.**

Claude Code read it correctly. **The wording did not say that**, and under a literal reading the
cheapest way to make a red gate green is to **re-introduce the bug on the new side** — a real hazard
in a deadline week, and the document's fault.

**THE RULE: when parity fails, the question is WHICH SIDE IS RIGHT — never how to make them match.**

| Situation | Action |
|---|---|
| New side wrong | Fix the new side. Gate did its job. |
| **Old side wrong** | Fix the old side or **retire it**. Record an **expected divergence** with row count and reason. **Never weaken the new side.** |
| Both wrong | Fix both; the gate was never the point. |

**An expected divergence is recorded, not suppressed. A gate that can be silenced by making the new
thing worse is worse than no gate.** Amended into the requirements at `[A 08-22]`.

Applied here: `mart_team_season_record` carries the defect and nothing should read it once
`srv_standings` is live — fix it or retire it, but do not un-fix the view to make the numbers agree.

### The null-identity sweep: one defect was five, and it went below serving

| View | Null identity | |
|---|---|---|
| `srv_standings` | 7,482 / 30,475 | **24.6%** |
| `srv_scoreboard` | 12,168 / 110,634 | 11.0% |
| `srv_team_game_log` | 12,552 / 221,268 | 5.7% |
| `srv_today_edges` | 9 / 211 | 4.3% — **the landing page** |
| `srv_rankings` | 662 / 49,798 | 1.3% |

**Cowork's ~4% estimate was low because the exposure is not uniform — it tracks how much non-FBS
schedule a view covers.** Estimating from the week-1 slate systematically understated views that
reach further back.

It also went deeper than serving: `fct_team_record.school` came from `dim_team`, so **the mart itself
was null on those 7,482 team-seasons** and everything reading it inherited that. The rule now lives in
a macro rather than a comment. All ten views clean.

### The selector guard — the ancestor assertion is the better half

Cowork suggested a **count threshold**; Claude Code used **membership by name**, because *"a threshold
drifts and gets raised"* — the first time someone legitimately removes a model, the fix is to lower
the number, and then it protects nothing.

**And it asserts every ancestor is selected**, which is the subtler failure Cowork did not think of:
*"a view rebuilt from an input that wasn't looks fresh and isn't."* Verified by reconstructing the
morning's manifest — it names all seventeen serving views as unreachable.

### Rule worth keeping verbatim

**"A client may be newer than the server it dumps from, never than the one it restores into."**
`pg_dump` 18 emits `SET transaction_timeout = 0` (added in PG 17), which the 15 server rejected
outright. The image now carries client 15 and picks the binary by asking the server its version —
the right general fix, not a workaround.

### Standings breadth — seven of nine ship without B1

Naming only, built name wins: `wins`/`losses` = `overall_wins`/`overall_losses` · `school` =
`team_display` · `logo_source_url` = `logo_url`.

Genuinely absent and **all derivable from `fct_game_team` today**: `division` · `conference_win_pct` ·
`current_streak_display` · `last_5_display` · `home_record_display` · `away_record_display` ·
`ats_record_display` (exists on `srv_team_overview` — carry it across **with the null-not-zero fix**).

`division` is ~8% populated post-realignment and AC-5.2 says group by it *"where a conference has
them"* — **absence must render as normal, not as missing data.**

Deferred to B1 correctly: `sp_plus_rating`, `elo_rating`.

### Order

1. Light scores-only refresh DAG — 2 API calls vs 31
2. Standings breadth
3. B1 `fct_team_week_rating`

Calibration parked until Week 5. Six days to Week 0.

## 2026-08-22 — "Green and useless" is now a pattern; deploy key decided; the post-game path is tested

PR #21 green. 264/264 dbt · 229/229 on the production selector · 41/41 page queries · 199 pytest.
**A4 is complete** — Matchup, Odds Board, Line Movement, Stats, Data Dictionary and Methodology all
shipped in #20. Every page has a body except Players.

### DECIDED: dedicated restricted deploy key

Nothing publishes to the droplet. `src/publish_marts.py` runs over SSH from Claude Code's machine and
no DAG calls it — so even with dbt now rebuilding the serving layer on schedule, **the website's data
only changes when someone runs publish by hand.**

Claude Code stopped rather than mounting a root key into the scheduler. That was the right call and
is worth more than the round-trip it cost.

**Chosen: a dedicated keypair used only by Airflow**, locked in `authorized_keys` with a **forced
command**, `no-pty`, no port/agent/X11 forwarding, and `from=` restricted to the Airflow host. With
the forced command the key cannot open a shell, read a file or forward a port — it can run one
script. **Blast radius goes from "root on the droplet" to "can trigger a publish"**, and it revokes
by deleting one line with no effect on Marc's own access.

**Premise to check first: does publish need root at all?** Loading a Postgres schema needs a
*Postgres role*; the Unix user is probably incidental to how the droplet was provisioned. If so, a
purpose-built `cfdb_publish` user costs nothing extra and makes the forced command belt-and-braces
rather than the only control.

**Publish runs as a downstream task of the dbt build, never on its own schedule.** A clock-triggered
publish can fire mid-build and ship a half-rebuilt serving layer — and succeed while doing it. Same
signature as everything else this week.

**Post-publish verification added:** row counts on the droplet against the transform tier per `srv_`
view, failing the task on mismatch. Publishing is the last hop before a user sees data and was the
only hop with no check on it.

### THE PATTERN: green and useless — three instances in four days

**`+tag:production` resolved to six models. Three legacy marts and three staging models. Not one
`srv_` view, not `fct_game`.** The refresh fetched results, landed them in raw, rebuilt three marts
nothing reads, and stopped. Every serving view the site reads was rebuilt only by hand. Now 53 of 58.

| # | Finding | What succeeded | What it produced |
|---|---|---|---|
| 1 | Deploy tree 9 commits behind | a full dbt build | would have **reverted** a day's fixes |
| 2 | `->> '0'` on a JSON array | the extraction | null, masked by a working fallback |
| 3 | `+tag:production` = 6 models | the scheduled refresh | nothing any page reads |

**All three were green. None was visible from run status.** The common cause: every check verified
that something **ran** and never that it **produced** anything.

**Standing guard adopted: assert what a selector RESOLVES TO, not just that it succeeds.** A test
failing when the production selector returns fewer than N models — or when any model backing a `srv_`
view is absent from it — would have caught this the day the tag was introduced. Claude Code already
built this exact shape for the missing conference segment; it generalises.

### The 11% unnamed teams is a dimensional lesson

`srv_scoreboard` could not name **12,168 of 110,634 rows**. It took the display name from `dim_team`,
built from CFBD's `/teams` — which does not list every opponent an FBS side schedules. A Division II
visitor exists in `/games` and not in `/teams`. The page rendered an em dash for the team, `None` for
the winner, and a null slug — a link to nowhere.

**The rule: `/games` is the authority on WHO PLAYED. `/teams` is the authority on WHO IS AN FBS
PROGRAM.** Different sets, and the fact table's key space is the larger one. Any model assuming the
dimension covers the fact's keys is wrong by about a tenth.

`srv_schedule` was already right because it took the name from the game. Same data, two sources, one
complete.

**Cowork's estimate was low by more than half** — the sample review put incomplete slug coverage at
~4% from the week-1 slate; the real figure is 11%.

Also fixed: the Scores page **re-derived the winner in Python** from the sign of a nullable
`actual_margin` while the view already carried `winner`. They disagreed on **1 game in 295**. AC-G.2
exactly — two derivations of one definition; the view wins.

### What the rehearsal cleared is worth as much as what it found

**164/164 home wins carry a negative `actual_margin` on screen.** Game log subject-team oriented on
every win. All seven box-score columns populate. Standings records compute. Matchup series
reconciles.

That was the largest untested surface on the site. Three completed games are now pinned in CI
permanently — including one against a team deliberately absent from `raw_teams`, and one tie — so
both branches run on every build. Third use of the prove-it-by-breaking-it pattern.

### Cadence: improved, but the timing problem stands

A third DAG exists now — `cfbd_midweek_results`, Thursday 12:00 UTC. It fires **ten hours before
Thursday's 22:00 kickoffs**, so opening night's 20 games and Saturday's 51 both land Sunday 30 August
without a lighter refresh. A full refresh is 31 API calls; a games-only fetch is 2.

### Order from here

1. Deploy key + publish DAG + post-publish row-count verification
2. Light scores-only refresh DAG
3. Standings breadth — eight columns the requirements name and the view lacks
4. B1 `fct_team_week_rating`

Calibration stays parked until Week 5.

## 2026-08-21 (evening) — DIRECTION: model tuning parked until Week 5; breadth and Week-0 usefulness are the priority

**Marc:** *"Model prediction doesn't really become important until Week 5 when the 2026 data is
mature enough to use. So, we have time. The breadth/accuracy of the tables, and how functional and
useful the website is, is important with Week 0. Let's push forward with building the website,
improving the data model, and making it useful and informative for users. Once we get things to a
better spot, we'll spend considerable time fine-tuning predictive capabilities."*

**Calibration work is parked.** The decile segments Claude Code built stay — they are correct and
they will be waiting. No recalibration, no decile-curve investigation, no modelling decisions until
after Week 5. This is a simplification, and it frees the whole runway for data breadth and site
usefulness.

### The finding that reorders the queue: the post-game path has never rendered real data

Every page built so far was verified against **2026 fixtures**, and every 2026 fixture has
`is_completed = false`. From `srv_sample.xlsx`, all null on every sampled row:

| View | Never-exercised columns |
|---|---|
| `srv_scoreboard` | `home_points`, `away_points`, `winner`, `actual_margin`, `is_upset`, `excitement_index`, `attendance` |
| `srv_schedule` | `home_points`, `away_points` |
| `srv_team_game_log` | `points_for`, `points_against`, `result`, `margin`, and every box-score column |
| `srv_matchup` | `home_points`, `away_points`, `actual_margin` |

**The pre-game render path is proven. The post-game path has never executed against real values
anywhere on the site.** Scores, the Schedule post-game card state, the Team page game log, Matchup's
result block and Standings' records are all first-run on Thursday night, live.

Not a build error — 2026 is legitimately what is upcoming. But it means **opening weekend doubles as
the first integration test of the half of the site that matters most on a Saturday**, and the
`actual_margin` sign convention sits inside that path.

**The distinction worth recording:** the sign convention has been verified **3,402/3,402 in the
data**. It has never been verified **on screen**. A display layer that flips a sign is a different
bug from a model that does, and only one of the two has been ruled out.

**DECIDED: rehearse against a completed 2025 week before Thursday**, then keep a completed-2025-week
fixture in CI permanently so the post-game path is exercised on every build rather than four times a
season.

### Open operational question, raised not concluded

As of the 2026-08-17 audit, `cfbd_results_refresh` ran **Sunday 12:00 UTC**. If that is still the
cadence, the first FCS games (Thu 27 Aug) and first FBS games (Sat 29 Aug) do not show as final until
**Sunday 30 August** — the Scores page stale for the entire opening weekend.

I cannot verify the current schedule from here and have asked rather than assumed. If it is still
weekly, it outranks every remaining page: *a Scores page showing Thursday's games as "scheduled" on
Saturday morning is worse than not having the page.* The fix pattern already exists — the same
season-aware gate that drives the lines cadence.

### Revised order

| # | Work | Why |
|---|---|---|
| 1 | **Post-game rehearsal against completed 2025** | Untested path, cheap, data already there |
| 2 | **Confirm / fix results-refresh cadence** | Potentially a three-day-stale Scores page on opening weekend |
| 3 | **Matchup** | The decision surface, and the click target for every row on the site. *A site where rows are clickable and the destination is thin is worse than one where they are not clickable at all.* |
| 4 | **Odds Board, Line Movement** | Market data needs no model — fully useful from day one |
| 5 | **B1 `fct_team_week_rating`** | Reframed by Marc's direction as a **breadth** item, not a de-partialer |
| 6 | Stats, Data Dictionary, Methodology | Breadth; the last two are portfolio-weighted rather than Saturday-weighted |
| 7 | A5 Excel Export | |

**B1 gets more important under this direction, not less.** SP+, Elo, SRS and adjusted EPA are the
numbers that make a team page worth reading, and in weeks 1–4 — with no model to look at — they are
the most informative content the site can carry.

### Cheap breadth worth taking if there is room

All landed in raw, none needs a model: `fct_game_weather` · **the venue join key** (`fct_game` carries
a venue *name*, not an id — one key unlocks rest, travel and elevation, three of the most interesting
context columns on Matchup) · `network` from `raw/games_media` · `excitement_index`, which 112,272 raw
games already carry and which is the best "was this worth watching" signal available.

**The venue key is the best value of the four** — one join key turns Matchup from a table into a
preview.

## 2026-08-21 (later) — The alarm paid for itself in a day; the model is miscalibrated in the direction that costs money

262/262 dbt on production and on a clean CI reproduction · 41/41 page queries · 196 pytest · flake8
clean. Serving republished, site deployed.

### A6 caught the worst class of failure there is

The deploy tree was **9 commits behind main** while still holding the old `dim_team.sql`,
`srv_matchup.sql` and `srv_team_overview.sql`. Tonight's scheduled dbt build would have rebuilt the
serving layer with **the logo fix, the tie fix, the scoreboard columns and the ATS null all
reverted** — and it would have **succeeded**.

**Green, silent, destructive. Nobody investigates a passing job.** The first symptom would have been
someone noticing the logos were gone again.

`ERROR: Deploy tree is 9 commits behind main`. Pin advanced, full build from the deployed tree,
260/261, fixes verified intact — 32,827 logos, 40,045 tie-corrected series rows. Alarm back to `ok`.

**The structural point worth keeping: the pin protects production from dev, the alarm protects
production from the pin, and neither is optional.** Shipping the pin without the alarm would have
been a net loss. Two days ago that alarm was a paragraph in a build order.

### The calibration finding, and the consequence nobody had spotted

`srv_model_performance` went from 6 rows to **193** across five cuts — overall, week, conference,
confidence, probability decile.

**`xgboost_home_win_calibrated` is measurably miscalibrated**, which is worth saying plainly because
the name asserts otherwise:

| Band | Says | Actually won | |
|---|---|---|---|
| 80–90% | 0.855 | **0.929** | underconfident |
| 40–50% | 0.459 | **0.329** | overconfident |

**Both points move the same way: predicted probabilities are compressed toward 0.5.** The model
understates favourites and overstates underdogs — the classic signature of over-regularisation, or of
a calibration step fitted on a different distribution than the one being scored.

**THE CONSEQUENCE, which is the reason this matters beyond one page.** Edge = model probability −
market probability. If model probabilities are systematically compressed toward 0.5, that difference
is **systematically biased toward underdogs**. When Edge Finder goes live in Week 5 it will surface a
disproportionate number of underdog "edges" that are artifacts of miscalibration rather than value —
and they will look exactly like the good ones.

**This is the single most plausible way this site loses money, and it is invisible on every accuracy
metric.** 73.2% straight-up reads identically whether the model is calibrated or not. No accuracy
figure shows it. That is precisely the argument for the page existing.

**Next step recorded, decision deferred to Marc:** pull the full ten-band decile curve per model —
two points suggest compression, ten will show whether it is monotonic and how severe. If systematic,
the options in order of preference are (a) recalibrate with isotonic or Platt on held-out data and
compute edge off the recalibrated probability, storing both with a method column exactly as
`devig_method` is stored; (b) ship as-is with the miscalibration stated **on Edge Finder**, not only
on Model Performance; (c) withhold probability-based edges until fixed — spread edges are unaffected.

**Never quietly adjust probabilities to make the curve look better.** Store the raw output, add the
calibrated one alongside, let the plot show both.

**The calibration plot is now the most valuable chart on the site.** A model that says 85% and wins
93% is a better story than a model that says 73% accurate — the first is a claim you can check, the
second is a number you have to trust.

### COMPOSITION DEFECTS — naming the class, and two criteria I owed

The ATS rate was displayed beside `games` = 567 while computed over `cover_scored` = 553. Pushes are
correctly excluded from numerator and denominator; the **displayed n** included them.

**Both numbers were individually correct. Placing them adjacent asserted a relationship that did not
hold.** Same family as the `->> '0'` silent null — every component behaves correctly and the assembly
is wrong. **Composition defects are invisible to component-level testing by construction**, which is
why a criterion has to name the *relationship*, not the parts.

Two of my criteria were underspecified and are amended:

- **AC-G.33** — was "renders with its `n` adjacent" and never said *which* `n`. Now: the `n` shown
  must be **the denominator the rate was actually computed over**.
- **AC-G.32** — had two states; there is a third. Now **null `—` / zero `0` / not-applicable `n/a`**
  with a hover. A bare em dash for `cover_scored = 0` reads as missing data and invites "when will
  this fill in?" — the answer is never. *"We don't have it yet"* and *"this doesn't apply here"* are
  different claims.

### Conference double-counting is correct, and the page says so

A game counts under both conferences, so conference rows exceed the overall row. That is the right
answer — *"how does the model do on SEC games"* includes a visitor's trip to Tuscaloosa — and the
page states it rather than letting a reader sum the column and conclude the site is broken.

### Two practices worth making standing

- **Prove a guard by breaking it.** The CI fixture's prediction payloads carried no conference, so
  that branch of the union produced nothing and the whole segment was absent **with nothing to say
  so**. The new test naming any missing cut was verified by *deleting the rows and watching it fail*.
  Second time in two rounds a guard has been proven by deliberate breakage.
- **A check that passes for the wrong reason is worse than no check.** `check_page_queries.py`
  refused to substitute `*` for `{MEASURES}` rather than guessing — *"it proves the table exists and
  nothing about the columns, which is the whole point."* It now resolves module constants by parsing
  the file. A false pass spends the credibility of the checks that work.

### Next: B1

`fct_team_week_rating` is the last thing making pages partial — Team page Ratings and Trends,
Matchup, team profile percentiles. Build from CFBD's landed ratings endpoints (`/ratings/sp`,
`/ratings/elo`, `/ratings/srs`, `/wepa`, `/ppa`). **Never from the pack's `training_data.csv`**, which
ships 5,133 games of exactly these features pre-assembled — this is the one model where the
provenance trap will actually be tempting.

## 2026-08-21 — The silent-null bug class, and two guards that caught what review would not

Four fixes landed from the `srv_sample.xlsx` review, plus A6. 254/255 Postgres · 231/232 Databricks ·
254/254 CI · 170 pytest. Nine of eighteen pages rendering real data before this round; the deploy
tree, logos, ATS zeros and the Week-5 floor all resolved in it.

### The logo bug is a CLASS, and it is the most transferable thing to come out of this project

`dim_team.logos` held a populated array of CDN URLs on **all 34,061 rows**. The extraction used
`->> '0'` — the **object-key** accessor. On a JSON array that looks for a key named `"0"`, finds
none, and returns null.

Three reasonable things stacked into an invisible failure:

1. **An accessor that returns null on type mismatch** rather than erroring.
2. **A format where a missing key and a null value are the same answer.** No warning is possible.
3. **A graceful fallback that worked perfectly.** The AC-G.28 monogram fired 100% of the time and
   the site looked fine.

**The fallback is what made it invisible.** A safety net that always fires *is* the design, and
nobody inspects a design. Six views, every logo column, and it passed every test in the project
because nothing asserted the columns had values.

Fixed with a distinctly-named dispatched macro, `json_array_element_string`, so the confusion cannot
recur by autocomplete. **32,827 of 34,061 populate — 96.4%.**

**The generalisation worth keeping:** any column extracted from JSON needs a **populated-rate** test,
not a `not_null` test. `not_null` would fail forever on the legitimate 3.6% and get muted; a
`severity: warn` threshold at ~90% would have caught this on the first build. And every `->>` in the
project deserves one sweep against its source's actual JSON shape — 65 raw tables of CFBD payloads
will not have only one array in them.

### Two guards caught what review could not, in two consecutive rounds

- **AC-G.2, the no-arithmetic/one-relation contract test**, caught
  `where team = (select max(team_display) from srv_team_overview …)` — two relations in one query
  wearing a filter's clothing. It contains no `JOIN`, reads as a scalar, and the intent was
  reasonable.
- **The CI layering guard** caught `srv_system_health` reading `stg_deploy_status` directly — serving
  building on staging — **minutes after the rule was written**, and against the person who wrote it.

Both were reasonable-looking code written with correct intent, which is exactly the class review
misses. Claude Code's resolution to the second is the right principle: *"a boundary with an exception
carved in for one convenient case isn't a boundary."* `fct_deploy_status` as a thin mart costs almost
nothing.

### A6 landed with two design choices worth adopting as patterns

**It deliberately does not auto-advance the pin.** Auto-advancing would hand back exactly the
protection the worktree pin exists to provide. An alarm that fixes itself is a scheduler.

**The CI fixture carries a stale row rather than a healthy one, so the escalating branch runs on
every build.** Claude Code's phrasing: *"An alarm never seen firing is an alarm nobody knows works."*

That generalises. `srv_system_health` now carries five signal types — freshness, data_quality,
documentation, quota, deployment — and only one has had its escalating branch exercised. Current data
is 220 ok / 3 warn / 1 unknown, so `error` is untested everywhere. **A trip-the-threshold fixture per
signal type**, so the severity column is tested rather than assumed on the Saturday in October when
something actually breaks.

### Also landed

`training_week_floor` on `srv_today_edges` and `srv_matchup`, so the Week-5 empty state is
data-driven. `team_slug` on `srv_teams_index`, `srv_standings`, `srv_team_game_log`. ATS displays now
null for ungraded seasons — 684 rows corrected; 2025 teams with graded games still show real records.
Deploy tree moved PR #17 → #19: Airflow now sees 56 models, not 39.

### Outstanding from the sample review

- `segment_type` / `segment_value` on `srv_model_performance` — the one that unblocks real page
  content (by-week, by-conference, calibration decile). Everything else on that page renders.
- `cover_scored = 0` must render em-dash, never `0.0%` — **the same manufactured-zero class as the
  ATS `0-0-0` just fixed**, so worth doing in the same pass as anything touching that view.

### Remaining on A4

Stats, Matchup, Odds Board, Edge Finder, Line Movement, Data Dictionary, Methodology. Then A5 (Excel
Export, now its own task). Seven days to Week 0; nothing on the critical path blocked.

## 2026-08-20 (late) — The column audit: 77% of required serving columns absent, and a pattern named

**CORRECTION to the entry below (2026-08-20 evening).** That entry said *"the cutover gate is met."*
It is met for **two of three** published marts. See the gate section at the end of this entry.

### The systemic finding

Claude Code audited the built serving views column-by-column against the requirements. **104 of 135
required columns are absent — 77%.**

| View | Required | Present | Missing |
|---|---|---|---|
| `srv_matchup` | 31 | 7 | 24 |
| `srv_model_performance` | 17 | 1 | 16 |
| `srv_today_edges` | 23 | 8 | 15 |
| `srv_edge_finder` | 19 | 4 | 15 |
| `srv_team_stats` | 16 | 3 | 13 |
| `srv_rankings` | 17 | 5 | 12 |
| `srv_schedule` | 12 | 3 | 9 |

The most-missed are structural rather than incidental: `as_of_ts` absent from **all seven**;
`start_date_et` from four; `*_slug` from three **with no slug column anywhere in `dim_team`**;
`attribution` from three.

**So v1.1's build order was unreachable.** Step 6 ("build the pages") could not follow steps 1–5,
because no step widened the views. Code flagged it rather than discovering it on page 3 of 18.

### The pattern, and why "check more carefully" is not the fix

Three rounds, three times the cheapest available signal was taken as evidence of readiness:

| Round | Signal | What it proved | Cost |
|---|---|---|---|
| v0 spec | three object names | those names existed | specified `fct_game_team` as new; it was production, 220,204 rows |
| v1.0 | "the page renders" | nothing about the database | two views marked built; both absent |
| v1.1 | "the view exists" | the view exists | **104 of 135 columns absent** |

Not three unrelated slips — **a standing willingness to treat the easiest observable as the thing
actually needing to be known.** "Check more carefully" has failed three times, so v1.2 adds a
definition with a gate instead of another resolution.

**DECIDED — the readiness definition.** A page is **BUILDABLE** only when all three hold:
**EXISTS** (view in `serving`, both engines) · **COMPLETE** (every required column verified against
`information_schema`, not by inspection) · **PUBLISHED** (on the droplet, readable by the app role).
Anything less is NOT BUILDABLE, and the page section names which of the three failed.

**"Data ready" is withdrawn as a phrase** — it meant only EXISTS and read as all three. New criteria
AC-G.53 to AC-G.56 encode the gate: a completeness check that is *run*, not eyeballed; `as_of_ts` on
every view, `not_null`-tested; `team_slug` in `dim_team`; and a rule that a stale readiness line is a
defect in the document.

### DECIDED: widen in ONE PASS, and the foundation moves behind it

Marc's call. One PR, one parity run, no partially-contracted serving layer, no half-states during
cutover. **Cost accepted explicitly: nothing downstream is testable until it lands.**

This also settles Code's question in Code's favour — the shared foundation now sits *behind* the
widening. Building the team-identity helper, attribution component and query-param layer against
views about to gain 104 columns means writing them twice.

### Two things that were impossible, not merely unmet

- **`serving` is not on the droplet at all.** `publish_marts.py` ships exactly three tables into a
  `marts` schema. **AC-G.4's inverse is what is true today** — `marts` is the only thing the site
  can read. Publishing `serving` is now build step 2, ahead of the repoint.
- **No slug column exists in `dim_team`**, and AC-G.14 forbids deriving one in Python. **Every deep
  link on the site turns on that one dbt change.**

### The gate correction, and the freshness decision

| Published mart | Parity pair | Status |
|---|---|---|
| `mart_team_season_record` | `srv_standings` | test exists — **gate met** |
| `mart_team_schedule` | `srv_team_game_log` | test exists — **gate met** |
| `mart_data_freshness` | — | **no like-for-like pair** |

`srv_system_health` unions freshness with three other sources, so a parity test is the wrong
instrument for it.

**DECIDED: retire the freshness banner rather than build a parity pair.** AC-G.35 already requires
per-page `as_of_ts` from each page's own view, and `as_of_ts` is in step 1 regardless — so the banner
is redundant, retiring it removes the last `mart_*` read, and detailed endpoint freshness is
back-of-house content that AC-1.7 always placed on System Overview.

**The distinction worth keeping:** the gate applies to a **cutover**, where a live element starts
reading a different object. Retiring an element is not a cutover, so no proof is owed. Declaring
`srv_system_health` a supersession *would* have been one, and would have needed a proof neither side
can produce — which is why that option was refused rather than taken as the fast path.

### Page-level corrections

- **Page 16.** Both `dim_field_metadata` and `srv_data_dictionary` are **957**; the "957 / 834" was
  two build times, not two objects. `dim_field_metadata` is a **view over the live catalog**, so its
  count moves whenever a model is added — never quote it as fixed. **Coverage is 30.5% (292 of 957),
  down from 41.6%**, because views were added faster than descriptions. AC-16.3 now says the page
  renders the current figure whatever it is: *a coverage metric that only ever goes up is a metric
  someone is managing rather than measuring.*
- **AC-16.6 rewritten.** It was **trivially true** — the view reads `information_schema`, so every
  serving column appears by construction and the test proved nothing. Replaced with the criterion
  that is currently false: every `srv_` column has a non-null description, failing for **69%**. Set
  to `warn` until coverage clears a chosen threshold, then `error` — *a test that fails 665 times on
  day one gets muted; one that warns and is tracked gets paid down.*
- **`description_status` is a new column**, not a rename. The view carries only `is_documented`
  (boolean), which cannot distinguish authored from from_openapi from UNDOCUMENTED.
- **Page 18.** `fct_endpoint_freshness` is built as `mart_data_freshness`; **`fct_pipeline_run` does
  not exist at all.** That section renders Degraded per AC-18.7 rather than presenting a
  non-existent object as a source.
- **AC-13.1** is right about the numbers and wrong about the shape — `srv_model_performance` carries
  1 of 17 required columns and has no segment structure.

### What Code assessed as needing no change

**Part 0, the Edge Finder decision, the provenance rule, the licence asymmetry.** Part 0 has now
survived two reconciliations untouched — the strongest available evidence that it is the part of the
document worth trusting. Worth noticing *where* the errors have and have not been: Part 0 was written
from first principles; every error so far has been in the parts written from assumed state.

### Build order now

1. **Serving completeness pass — one PR** (widen seven views, `dim_team` identity columns,
   `as_of_ts` everywhere, attribution onto prediction views, segment structure, `description_status`,
   plus `srv_team_overview` and `srv_odds_board` built to spec)
2. Publish `serving` to the droplet; scope `cfdb_read` to it, revoke `marts`
3. Repoint the app; retire the freshness banner
4. Shared foundation
5. Build the 18 pages
6. `fct_edge_bucket_performance`
7. CFBD adjusted metrics (v1.5)
8. Players → 18 of 18

`fct_team_week_rating` still primary on zero pages. Still waits.

## 2026-08-20 (evening) — Reconciliation: two wrong inferences, one framing error, three criteria decided

**PR #18 landed Tasks 0, 4, 5 and 6 before the requirements were read.** Worktree pin done (both
prior incidents reproduced in the working tree, neither reached production). `fct_poll_rank` 49,798 ·
`fct_team_season_stat` 177,876 · `dim_field_metadata` 834 · `fct_dq_test_result` 153. `home_cover_edge`
moved into `fct_prediction` with `is_cover_edge_from_export`. De-vig landed as `fct_market_probability`,
overround 1.0516, `devig_method` stored. `srv_matchup` and `srv_today_edges` built.

**245/245 Postgres · 225/225 Databricks · parity holding on DERIVED VALUES, not just row counts.**
That last clause is the version of the parity test worth having.

### Task 1 worked, and it cost less than the build it prevented

The requirements shipped with a confidence column marking which serving-view statuses were fact and
which were inference. **Two inferences were wrong**, and they were wrong in the expensive direction:

| View | Document said | Reality |
|---|---|---|
| `srv_team_overview` | inferred built — page renders | **ABSENT** |
| `srv_odds_board` | inferred built — page renders | **ABSENT** |

Six others the document called blocked or absent turned out built — harmless, and explained by PR #18
landing between writing and reading.

**Recording the mechanism, not just the outcome:** marking inferences as inferences and making the
first task "correct me before you build on this" is what converted a wrong document into a cheap
round-trip. Keep that pattern on any spec written without direct access to the thing being specified.

### The framing error, which is mine

The document said **"13 of 18 pages render."** That was a claim about *data readiness* — which views
exist — and it read as a claim about *the site*. It is not.

**The deployed app is a 100-line single-page prototype reading `mart_*` directly.** Against Part 0 it
has `cache_data` and nothing else: no `st.navigation`, no `st.Page`, no `query_params`, no
`color_on_light`, no attribution, no explicit `LIMIT`.

**Two counts, never to be conflated again:** 15 of 18 serving views built; **1** page actually
rendered, and it does not read `serving` at all. The strangler cutover happened for the transform
tier and **has not happened for the site**. v1.1 carries both counts separately.

### DECIDED: Edge Finder ships without its calibration layer, and says so

`edge_bucket`, `bucket_hit_rate` and `bucket_n` **do not exist anywhere in the model.** Building the
aggregation is a new mart, not a column.

Uncomfortable, because the hit-rate slider is the control argued hardest for — *"the one that
actually protects you."* Shipping without it means shipping an edge list filtered only by magnitude,
and magnitude is the seductive number rather than the protective one.

**Resolution: ship the magnitude slider; render the hit-rate slider, the `n` column and the
calibration panel as Degraded**, naming `fct_edge_bucket_performance`. Plus a new AC-12.3b — the page
carries a visible statement that edges are ranked by magnitude only and that magnitude alone does not
indicate value.

**The rule behind it, worth keeping:** a control that is visibly absent is honest; a control that
silently defaults to 0 is a false protection, which is worse than none. Never ship the hit-rate
slider defaulted to zero as a stopgap.

### DECIDED: Stats ships raw team stats only; adjusted is v1.5

`stat_scope` and `stat_basis` do not exist. Opponent-adjusted metrics are not modelled and — per the
publication boundary — **must come from CFBD's `/ratings` and `/ppa` endpoints, never from the pack's
`training_data.csv`.** The pack ships those features pre-assembled, which is exactly the convenience
the provenance rule exists to refuse. Claude Code flagged this correctly and unprompted.

So Stats renders now from 177,876 real rows, with the four-way toggle Degraded. Page-readiness wins
over completeness, per the north star.

### DECIDED: the cutover gate is met — repoint the app off `mart_*` now

The evidence-based freeze rule gates a **cutover on the parity test passing, not on a date**. 245/245,
225/225, parity on derived values. **The gate is satisfied**, so repointing the site to `serving` is
authorised eight days before kickoff and does not wait for 7 September.

**This is the case the rule was written for.** Under the old calendar rule it would have been an
argument; under the evidence rule it is a question with an answer.

### Also decided

- **AC-G.41 was false, not unmet.** `attribution` exists only on `srv_model_performance`;
  `srv_edge_finder`, `srv_matchup` and `srv_today_edges` render predictions without it. Reclassified
  from a check to a build item, ahead of the pages, because the shared attribution component has
  nothing to read otherwise.
- **AC-G.40 was underspecified.** A paint budget stated without a filter is not a criterion.
  `srv_matchup` at 110,634 × 65 must never be queried without `game_id`.
- **`is_out_of_sample_week` adopted as-is** — a week-level flag, not prediction-level. Sufficient for
  separating backtest from live, and arguably more honest since out-of-sample-ness is a property of
  the training cut. **But the UI copy must say "out-of-sample week", not "out-of-sample
  prediction"** — different claims, only one true.

### Where the project stands

Data tier is ahead of the app tier. Remaining work is nine items, **app-first**: shared foundation →
repoint → attribution join → `srv_team_overview` → `srv_odds_board` → build the pages →
`fct_edge_bucket_performance` → CFBD adjusted metrics → Players.

`fct_team_week_rating` is still the largest enrichment in the backlog and still primary on zero
pages. It still waits.

## 2026-08-20 (later) — Wireframe v0.3 and the site requirements contract

**Marc:** *"We need requirements that we can pass to Code to build to the wireframe."* Chosen shape:
wireframe first, then requirements for all 18 pages at **contract + acceptance-criteria** detail.
Both delivered.

### `cfdb_wireframe_v03.html` — 18 pages

**The Player page is back**, and the reason is worth recording because it is the matrix earning its
keep. Building the page-to-mart matrix surfaced that `fct_play` and `fct_player_game_stat` had
**zero pages referencing them**. A fact table nothing reads is either unjustified or evidence of a
missing page. Here it was the page — v0.2 had no player-level drill-down despite the project notes
calling for one.

**Every nav dot is now evidence rather than intent.** Dots re-derived from what the database can
actually serve: 13 of 18 render, 4 of those degraded, 5 blocked. Blocked pages name the specific
table that unblocks them, on the page itself.

Also updated: Model Performance carries the real Model Pack numbers (3,402 predictions, 6 of 7
models, 2025 held-out split); Edge Finder gains the out-of-sample flag and the de-vig disclosure;
attribution shown as a rendered element rather than a footer.

### `cfdb_site_requirements.md` — the build contract

18 pages, **208 numbered acceptance criteria**, per-page serving view with required columns, controls
and the four states.

**Structural choices worth carrying forward:**

- **Acceptance criteria are testable statements**, worded close to executable. `AC-12.3` is a thing
  you can check, not a thing you can interpret.
- **Precedence is stated explicitly:** `decision_log.md` > requirements > `roadmap.md` > wireframe.
  Removes the "which document wins" round-trip that has cost time twice already.
- **Column names are requirements on the serving layer, not descriptions of it.** Where a view
  already exists with a different name, **the built name wins** and the doc is amended. This is the
  guard against the class of error that produced the `fct_game`/`fct_game_team` inversion — writing
  a spec from names rather than from the database.
- **The serving-view inventory carries an honest confidence column.** Five views are confirmed built
  or confirmed absent from build reports; the rest are *inferred* built from the fact that their page
  renders. Marked as inference. First task of any build round is to replace that column with
  `\dv serving.*` output.

### DECIDED: Empty and Degraded are different states and must never render alike

The requirement that does the most work for trustworthiness. "No games match your filters" and "the
rankings table has not been built" mean opposite things — one is the user's doing and one is ours —
and they look identical if both render as a blank panel. Four states per section, every page:
Loading / Empty / Degraded / Error, each forced and verified.

Corollary adopted: **blocked pages stay in the nav**, rendering Degraded and naming their blocker. A
site that hides what it cannot do teaches the user nothing; one that says "Rankings is waiting on
`fct_poll_rank`" is a portfolio asset.

### DECIDED: build order is unchanged, and Players is explicitly last

| Step | Work | Effect |
|---|---|---|
| 0 | Airflow worktree pin | runtime-path, nothing lands first |
| 1–4 | `fct_poll_rank`+`dim_poll`, `fct_team_season_stat`, `dim_field_metadata`, `fct_dq_test_result` | **17 of 18 render**, no API call |
| 5–6 | `srv_matchup`, `srv_today_edges` | two degraded pages go full |
| 7 | four player tables | **18 of 18** |

Players is last on merit, not preference: it is the only blocked page needing four tables and new
ingestion, where the other four each need one table off raw data already on disk.

`fct_team_week_rating` remains the largest enrichment in the backlog and is primary on zero pages.
It still waits.

### Carried forward unchanged

- **Airflow worktree pin** — now four reports old, two incidents behind it, season opens in 7 days.
- **`fastai_wp_predictions.csv`** — still never written; 6 of 7 models. Requirements handle it by
  making the missing model a **visible row marked not loaded**, not a shorter table (AC-13.4).
- **`cfdb_prompt_close_the_gap.md`** — written, carries the `postgres_only` lift and Tasks 0–3. Send
  it alongside the requirements.

## 2026-08-20 — First real predictions loaded; de-vig method decided; 13 of 17 pages render

**Marc ran the Model Pack notebooks.** 3,402 prediction rows across 6 of 7 models loaded into
`fct_prediction`. Edge Finder and Model Performance now render. **13 of 17 pages render**, up from
11; four remain blocked, each by one cheap table (`fct_poll_rank`+`dim_poll`, `fct_team_season_stat`,
`dim_field_metadata`, `fct_dq_test_result`).

### The sign convention held on real data

3,402/3,402 on both pinned tests — `margin == away − home`, and `(margin < 0) == home won`. The
defect most likely to produce confidently wrong numbers across every cover flag and ATS figure did
not occur. Worth recording that the verification was done against real output, not just the doc.

### First real accuracy numbers — 2025 held-out test split

| Model | Margin MAE | Winner | ATS |
|---|---|---|---|
| `ridge_margin_expanded` | **11.75** | **73.5%** | **51.4%** |
| `xgboost_home_win_calibrated` | — | 73.2% | — |
| `random_forest_score` | 12.77 | 68.8% | 48.6% |

**Context against the previously measured baseline** (Marc's own Performance Monitor, 2025 wks 5–8,
160 games): the prior model ran **margin MAE 14.13, SU 70.0%, ATS 49.4%**, against a market of
**MAE 11.24, SU 76.3%**.

So the pack's best model is a **material improvement**: MAE 11.75 versus 14.13 — now within about
half a point of the market's 11.24 — and ATS 51.4% versus 49.4%, roughly one point under the ~52.4%
breakeven at −110 rather than three.

**It is still not beating the market, and Model Performance ships saying so.** The comparison is
directional rather than exact — different model, different sample window — but the direction is
real and the honest framing is unchanged: this page exists to measure, not to flatter.

### DECIDED: `home_cover_edge` derivation is correct, but belongs in marts, not serving

The pack's notebooks populate **none** of the edge columns — `market_implied_home_win_probability`
and `home_cover_edge` are blank in all 3,402 rows. The contract permits "leave unsupported fields
blank" and every notebook takes that option.

Claude Code derived `home_cover_edge` from **the contract's own formula**, `spread − predicted_margin`,
and marked provenance with `is_edge_from_export`. **That is correct** — applying a documented
definition is not inventing a metric, and the provenance flag is the right guard.

**One change: move the derivation from the serving view into `fct_prediction`.** It is a per-prediction
measure, so leaving it only in `srv_edge_finder` forces `srv_model_performance` and the Excel export to
re-derive it independently — three copies of one formula, which is how definitions drift. Derive once
in marts, consume everywhere. Keep `is_edge_from_export`.

### DECIDED: de-vig method is **multiplicative (normalisation)**, with the method stored

`market_implied_home_win_probability` is blank in every export and cannot be derived without choosing
a de-vig method. Claude Code correctly refused to guess — that is a modelling call, not a load-time
one.

**Chosen: multiplicative normalisation.**
`implied_home = (1/home_decimal) / ((1/home_decimal) + (1/away_decimal))`

Why this one:
- It is the standard two-way de-vig, it is one line, and its assumption — vig is proportional to
  implied probability — can be stated plainly on the Methodology page. For a project whose
  differentiator is honest measurement, explainability outranks marginal accuracy.
- Shin's method and the power/logarithmic methods correct favourite–longshot bias better, but the
  improvement on two-way markets is small and the explanation is long.

**Two requirements that make the choice reversible:**
1. Store a **`devig_method`** column alongside the probability. The choice becomes auditable, and a
   second method can be computed later and compared without rewriting history.
2. The raw moneylines stay in `fct_betting_line` untouched — de-vig is derived, never destructive.

Document the assumption in `dim_field_metadata` when that lands.

### Loader defect worth recording, because the failure mode is deceptive

The loader reported "0 files" while six exports sat on disk — `--dir` had an argparse default, so the
explicit-path branch always fired and the candidate search never ran. **This is the second time this
failure mode has presented as "the notebooks haven't been run yet."** Fixed, and it now prints the path
it read.

A silent zero that mimics an upstream state is the worst class of pipeline bug. Printing the resolved
path on every run is the correct general fix and should be the pattern for any loader.

### Open, carried forward

- **`fastai_wp_predictions.csv` was never written** — notebook 04 completed but its export cell
  produced no file. 6 of 7 models loaded. Marc re-runs that cell; the loader picks it up.
- **The Airflow worktree pin** — now open across three reports, with two incidents behind it and the
  season opening in seven days.
- **`postgres_only` is NOT open** — decided 2026-08-19 (see that entry). Predictions may build on both
  engines. Claude Code has not yet received that decision; it is in `cfdb_prompt_serving_databricks.md`.

## 2026-08-19 (evening) — Predictions ARE permitted on both engines; postgres_only tag lifted

**Escalated by Claude Code:** predictions were tagged `postgres_only` and excluded from Databricks
pending a licence call, on the grounds that the pack licence prohibits uploading pack contents or
"substantial portions" to a notebook platform — and Databricks is literally a notebook platform.

**DECIDED: predictions may be built on both engines. Lift the `postgres_only` tag.**

The reasoning, from the licence text:

1. **The licensed dataset is never uploaded to either engine.** `training_data.csv` is not loaded
   anywhere — only `model_outputs/*.csv` is. So this was never a question about the pack; it is a
   question about derived output.
2. **Derived output is explicitly permitted.** *"You may: Use the data, notebooks, and generated
   outputs for personal analysis, academic research, or private projects."* Predictions are
   generated outputs in a private project.
3. **The export is not a substantial portion of the dataset.** The 42-column contract carries game
   identity, actuals, spread, and model output. **None of the pack's 86 training features appear
   in it** — no adjusted EPA, no Elo, no talent. It cannot be used to reconstruct the dataset.
4. **The prohibition is on uploading *pack files* to a notebook platform.** Predictions are not
   pack files. And the workspace is single-user Databricks Free Edition — private, not shared.

**The architectural cost of the cautious reading was real and is the tiebreaker.** Claude Code had
to write `srv_schedule`'s prediction columns and then revert them, because that view must build on
both engines. Keeping predictions Postgres-only creates a permanent class of serving views that
cannot build uniformly — a lasting complexity cost, and a hole in the checksum-verified dual-engine
parity that is one of the better engineering stories in this project.

**Caveat stated plainly:** this is Cowork reading a licence, not legal advice. The licence lists
`admin@collegefootballdata.com` for licensing questions. For a portfolio project that may be shown
to employers, sending that email and getting a written yes is cheap insurance — **worth doing, not
worth blocking on.** Proceed on the reading above; amend if the answer differs.

**Unchanged:** the pack itself stays out of git and off both engines. Attribution stays carried as
data in `dim_model_version` and `srv_model_performance` — Claude Code's choice to make it
structurally impossible to render the numbers without it is better than putting it in page config,
and is adopted.

### The critical path is now a manual step only Marc can take

`model_outputs/` does not exist. The notebooks have not been run, so **nothing in the prediction
pipeline is validated against real model output** — it is proven against a contract-shaped
synthetic export and a CI fixture carrying the awkward cases (negative `actual_margin` where the
home team won, blank actuals for an unplayed game, a week-1 out-of-sample row).

That is the right way to have built it, and it means the gate to 17/17 pages rendering is now:
**Marc creates the Python 3.11/3.12 venv, installs `requirements.txt`, runs
`00_modeling_workflow_overview.ipynb` and then notebooks 01–07, then
`python -m src.load_predictions`.** No further design work stands between here and the two blocked
pages.

### Still open, carried forward

- `srv_matchup` and `srv_today_edges` do not exist, so predictions cannot yet be wired into the
  Matchup and Today pages. Both pages render today; this is enrichment.
- The Airflow worktree pin — the other half of the production-safety fix, still outstanding after
  two incidents.

## 2026-08-19 (later) — SHIFT GEARS: Model Pack acquired; prediction assets become the priority

**Marc acquired the CFB Model Training Pack — 2026 Edition** (Rad Sports Analytics, LLC) and
extracted it to `claude_code/cfdb_model_pack/`. **DECIDED: integrating it into the data tier is now
the priority**, because it is what converts Edge Finder and Model Performance from blocked to
rendering and completes the north-star set — every page serving real data.

### The good news: the export contract is already written

The pack ships `Prediction_Export_Schema_2026.md` — a **42-column contract**, one row per
`game_id` + `model_name` + `split`, that every one of the seven modelling notebooks writes to. It
already contains nearly every column the Edge Finder and Model Performance wireframes need:

| Wireframe need | Column already in the contract |
|---|---|
| Edge Finder — edge | `home_win_probability_edge`, `home_cover_edge` |
| Edge Finder — bucket | `confidence_bucket` |
| Edge Finder — no-vig | `market_implied_home_win_probability` |
| Matchup — Pred scores | `predicted_home_points`, `predicted_away_points` |
| Matchup — Pred spread/total | `predicted_margin`, `predicted_total_points` |
| Model Performance — calibration | `raw_/calibrated_home_win_probability`, `brier_score_component`, `log_loss_component` |
| Model Performance — accuracy | `margin_error`, `absolute_margin_error`, `home_win_correct`, `cover_correct` |

**This is a load job, not a design job.** `fct_prediction` should adopt this schema more or less
verbatim rather than inventing one.

### FINDING 1 (HIGH) — the sign convention is inverted, and it is a landmine

The pack documents, and uses consistently across dataset, notebooks, exports and leaderboard:

```
margin        = away_points - home_points      <- AWAY MINUS HOME
negative margin means the HOME team won
home_cover    = True when margin < spread
spread        negative means the HOME team was favoured
```

`margin = away - home` is **inverted from the intuitive convention** and from how the site's own
Proj/Pred/PTL vocabulary reads. If the data tier assumes home-minus-away anywhere, every cover
flag, every edge, and every ATS number silently flips sign — and still looks plausible.

**DECIDED: adopt the pack's convention verbatim through raw and staging. Do not flip it in
transit.** If a serving view wants a home-perspective margin, derive it as a separate, explicitly
named column (`margin_home_perspective`) at that boundary. A silent flip mid-pipeline is the worst
outcome; an explicit derived column is auditable.

### FINDING 2 — this CLOSES the `spread` open question from 2026-08-17

Open since the first reconciliation: what does `spread` mean in the CFBD training data? The pack's
own Data Info Sheet answers it: **closing spread, negative means the home team was favoured.** The
`dim_field_metadata` known-unknowns register can move that field from UNKNOWN to DOCUMENTED, with
the pack cited as the source.

Caveat worth keeping precise: "closing" applies to *completed* games in `training_data.csv`. The
Tier-3 **weekly** drops (`training_data_2025_weekNN.csv`) are forward-looking, so their `spread`
cannot be a closing line — the *sign convention* carries, the word "closing" does not.

### FINDING 3 — the model cannot credibly predict Weeks 1–4, and the season opens Aug 27

Pack coverage: **5,133 games, 86 fields, seasons 2016–2019 and 2021–2025** (2020 deliberately
excluded), **regular season from Week 5 onward** — because the opponent-adjusted inputs need game
history before they mean anything. Default split: train ≤2023, validate 2024, test 2025.
Postseason present in the CSV but excluded by the notebooks by default.

**Consequence: there is no in-sample analogue for early-season games.** Predictions for Weeks 0–4
of 2026 are extrapolation, not inference. Edge Finder must not present them as if they carry the
same weight as a Week 8 edge.

**DECIDED:** ship the prediction pipeline now, but Edge Finder and Model Performance must **label
early-season predictions as out-of-sample** and default the edge threshold so they do not surface
as actionable before Week 5. This is the honest version and it costs nothing to build in from the
start.

### FINDING 4 (HIGH) — the licence changes the .gitignore answer

`cfdb_model_pack/LICENSE` — personal, non-commercial, original purchaser only. Explicitly
prohibits: *"Upload the pack files to a public repository, shared drive, data marketplace, or
notebook platform"* and *"Share the ZIP or its contents with people who have not purchased the
pack."*

**DECIDED: `.gitignore` the entire `cfdb_model_pack/` directory, not just `*.zip`.** Marc asked for
a `*.zip` pattern; that is not sufficient — the extracted notebooks, `training_data.csv`, and the
guides are the licensed material. The repo is private today, but going public has been contemplated
in this log, and a private repo with licensed data in its history is a landmine that survives the
`.gitignore` added later.

Two further licence consequences:

- **Generated outputs ARE permitted** for personal/private use, so `fct_prediction` holding
  predictions derived from the pack is fine.
- **"Present modified models or outputs as official CollegeFootballData.com predictions" is
  prohibited.** Edge Finder, Model Performance, Matchup and Methodology must attribute clearly:
  these are cfdb's own predictions built on a licensed training pack, not CFBD's.

### fct_prediction grain, reconciled

Pack grain is `game_id + model_name + split`. The earlier spec said `game_id × model_version ×
prediction_ts`. **DECIDED: `game_id × model_name × model_version × split`, plus `prediction_ts`**
so in-season re-scoring appends rather than overwrites. `dim_model_version` gains `model_family`
(seven families ship: linear margin, random forest scores, XGBoost WP, fastai WP, logistic WP, SHAP
XGBoost, stacked ensemble).

### Sequencing — unchanged north star, new top item

The NEXT set from this morning stands. This slots into it as item 5 and is now unblocked rather
than waiting: `fct_prediction` + `dim_model_version` take Edge Finder and Model Performance live,
completing 17 of 17 pages rendering.

## 2026-08-19 — NORTH STAR set: every page renders real data. Sequencing re-cut to serve it.

**Marc, stated plainly and recorded because it keeps getting re-derived away:**

> **The north star is real data serving every page of the website, as soon as possible, so the
> site can be built out and then iterated on. Not after Sep 7. Now.**

Everything else — model fidelity, phase purity, enrichment, dimensional orthodoxy — is
**subordinate to that.** Where a decision trades page-readiness against elegance, page-readiness
wins. Cowork drifted from this twice and Claude Code has re-derived the freeze three times; this
entry exists so neither happens again.

### The measurement that matters: pages that RENDER, not tables that exist

Prior analysis counted "pages blocked" as pages a missing table *touches*. That is the wrong
metric. The matrix already distinguishes **P** (primary — sets the page's grain, page cannot
render without it) from **S** (secondary — a column set, page renders thinner without it).
Recomputed on that basis:

- **11 of 17 pages render today.** Today, Schedule, Scores, Standings, Teams, Team page, Matchup,
  Odds Board, Line Movement, Excel Export, Methodology.
- **6 are genuinely blocked**, each by exactly one missing primary:

| Page | Blocked by | Source status |
|---|---|---|
| Rankings | `fct_poll_rank` (+ `dim_poll`) | raw on disk |
| Stats | `fct_team_season_stat` | raw on disk |
| Data Dictionary | `dim_field_metadata` | dbt schema.yml; upstream input generated 2026-08-18 |
| System Overview | `fct_dq_test_result` | dbt already writes `run_results.json` every run |
| Edge Finder | `fct_prediction` (+ `dim_model_version`) | Model Starter Package, arriving |
| Model Performance | `fct_prediction` (+ `dim_model_version`) | same |

**This corrects a recommendation.** `fct_team_week_rating` was proposed as the highest-leverage
build on the grounds that it "unblocks 9 pages". It is **primary on zero pages** — it enriches
nine and blocks none. It is the single biggest enrichment in the backlog and it should be built,
but it converts no page from broken to working, so it is not the north-star path.

### DECIDED: the NEXT set is seven tables, and it is the whole priority

`fct_poll_rank` · `dim_poll` · `fct_team_season_stat` · `dim_field_metadata` ·
`fct_dq_test_result` · `fct_prediction` · `dim_model_version`

Seven tables take the site from **11 of 17 rendering to 17 of 17**. Four have their raw already on
disk or their source already generated. Nothing in this set requires a new API call.

Everything currently labelled P2 — including `fct_team_week_rating` — is **enrichment and waits**.
A page that renders thinly is a page you can iterate on; a page that does not render is not.

### DECIDED: ML is scheduled, not deferred

`fct_prediction` and `dim_model_version` join the NEXT set. Marc is obtaining the Model Starter
Package and expects it within a day or two — several days before the first games. Those two tables
are primary on Edge Finder and Model Performance, which are the reason this project exists. Left
unscheduled, the build produces a well-engineered ESPN clone with no model in it.

The measured baseline (49.4% ATS, behind the market on every axis) is not a reason to delay —
it is the reason Model Performance ships early and honestly.

### The freeze, restated because it keeps being reapplied

Every table in the NEXT set is a **new object that nothing reads**. Per the 2026-08-18 BUILD NOW
entry, that is **not runtime-path work and carries no date constraint.** It does not wait for
Sep 7. It does not wait for Aug 27.

**The legitimate concern underneath the repeated freeze instinct is real, and the answer is not a
calendar.** A new model in the dbt project can fail the `dbt build` that also refreshes the live
marts. Fix that structurally: **dbt selectors or tags, so the production refresh runs an explicit
selection and a half-finished new model is incapable of breaking it.** Worth having before the
season regardless of what else is being built.

### Matrix v3

`cfdb_page_to_mart_matrix_v3.xlsx` replaces v2, which was stale enough to be actively misleading —
9 of 31 objects mislabelled, which is what made an audit of the repo read worse than reality. v3
carries verified statuses (6 dims, 6 facts, 6 serving views live) and a new **"Renders today?"**
column per page, so pages-touched can never again be mistaken for pages-blocked.

## 2026-08-18 (later) — BUILD NOW: full Phase 1 model in place for Week 0; freeze rule refined

**DIRECTIVE (Marc):** deferring the Phase 1 build to Sep 7 is not acceptable. The full data model
must be in place for **Week 0** so the site can be built out and iterated *before* real results
start flowing, not retrofitted around them. The time is now.

**Cowork's sequencing was wrong, and the reason is worth recording.** The previous plan
("spec now, build after Sep 7") conflated two different things: **building new objects** and
**cutting over to them**. The strangler migration adopted earlier this same day exists precisely
so that new construction is invisible to the running system — `mart_*` stays untouched and keeps
serving the site while `dim_*`/`fct_*`/`srv_*` are built alongside it. **New objects that nothing
reads are not on the runtime path.** Applying a runtime-path freeze to them contradicts the
migration approach that was chosen to avoid exactly that constraint. Building `dim_conference` or
`fct_game` touches neither `mart_team_schedule`, nor the publish job, nor the site.

**Week 0 is the right shakedown, and it is the argument for urgency.** The 2026-08-27 → 2026-08-30
slate is small (FCS-heavy Thursday/Friday plus the ESPN Saturday games) and real. A model that
cannot handle Week 0 is better discovered against ~20 games than against a 60-game Saturday. If
the model is not standing when Week 0 arrives, the first real data of the season lands somewhere
that cannot hold it, and the rest of the season is spent retrofitting.

**DECIDED: the freeze rule is refined from a calendar rule to an evidence rule where evidence
exists.** It replaces the flat "before Aug 27 or after Sep 7" for all cases:

| Change class | Constraint |
|---|---|
| **New objects nothing reads** (new dim_/fct_/srv_ models, new schemas, new tests) | **No freeze.** Build any time. Not on the runtime path. |
| **Cutover of an existing page to a new view** | **Gated on the parity test passing**, not on a date. Parity proves the swap is a no-op; a passing proof is stronger evidence than a calendar. |
| **Changes to existing runtime behaviour with no parity proof** (schedule changes, schema moves, publish-job rework, `search_path` changes) | **Still date-gated:** before 2026-08-27 or after 2026-09-07. |
| **Lines cadence gate** | **Exception. Must land by 2026-08-20** — the switch date, ahead of everything else. |

Converting the cutover gate from a date to a proof is what the strangler was bought for. Keeping
a date rule on top of a passing parity test would be paying for the safety mechanism twice.

**Target: Phase 1 model complete and validated against live Week 0 data.**

| When | What | Freeze class |
|---|---|---|
| by **2026-08-20** | Lines cadence gate + load step | exception, hard deadline |
| now → **2026-08-26** | `marts` layer: dim_team (promoted, +colour/logos), dim_conference, dim_venue, dim_season, dim_week, dim_provider, fct_game, fct_game_team, fct_betting_line | no freeze — new objects |
| now → **2026-08-26** | `serving` schema + srv_ views + **parity tests** against the live marts | no freeze — new objects |
| **2026-08-27 → 08-30** | **Week 0 as live validation.** Real games flow into the new model. Watch the tests, not the dashboards. | observation only |
| when parity passes | Site repoints to `srv_*`; `search_path` moves marts → serving; publish job follows | gated on proof |
| after **2026-09-07** | Anything still requiring a date-gated runtime change | date-gated |

**Consequences for the build:** the Phase 1 spec is still written first, but it is a **fast
spec-then-build in one arc**, not a spec parked for review until September. Cowork reviews the
spec as it lands rather than blocking on it. `mart_*` tables are not renamed, not dropped and not
repointed during this work — that is the whole point of building alongside them.

**Unchanged and still true:** the live site keeps reading `mart_*` throughout Week 0. Nothing
about "build now" means "cut over during the opening weekend." The parity test decides when that
happens, and it is allowed to say "not yet".

## 2026-08-18 — Serving layer named and separated; three layers, not two

**Origin:** Claude Code's structural finding while planning the `fct_*`/`dim_*` rename. Checked
the record and found `srv_` had **never been ratified** — zero hits in the decision log, the
roadmap or `CLAUDE.md`. It existed only in `cfdb_page_to_mart_matrix.xlsx`'s Serving_Views sheet,
load-bearing for everything under it. Recorded now.

**THE FINDING (Claude Code, accepted): the three existing marts are serving-shaped, not
fact-shaped.** `mart_team_schedule` joins team, opponent, conference and classification onto each
team-game row. `mart_team_season_record` carries school, conference and classification inline.
Both are pre-joined denormalized views — the workbook's own `srv_team_game_log` and
`srv_standings`. What exists today is **the serving layer, built first, with the dimensional layer
underneath it missing.** Renaming these to `fct_*` would mislabel them.

**DECIDED: three layers, with `srv_` ratified as the serving prefix.**

| Layer | Shape | Schema |
|---|---|---|
| `stg_*` | one row per source entity | `staging` |
| `dim_*` / `fct_*` | normalized; keys, not names | `marts` |
| `srv_*` | denormalized wide, pre-joined | **`serving`** (new) |

`srv_` over `src_`: `src_` reads as "source" and would sit confusingly beside `raw`.

**DECIDED: `srv_` gets its own `serving` schema in both engines** — consistent with the
schema-per-layer separation delivered 2026-08-17. Publish job and the droplet's
`search_path` move from `marts` to `serving`; the CI layering guard extends to the new layer.
Rejected: `srv_*` objects inside `marts` (re-creates the exact intermingling that work just
fixed), and denormalizing in the publish job (puts join logic outside dbt, breaking "dbt owns
all transforms").

**DECIDED: strangler migration, with a parity test as the cutover gate.** `mart_*` tables stay
untouched and keep serving the site. `dim_*`/`fct_*` get built underneath, then `srv_*` on top.
**A dbt test must prove each `srv_` view is row-for-row identical to the `mart_` it replaces
before the site swaps.** Nothing breaks at any point, and the parity test is a stronger artifact
than the rename it protects. Rejected: in-place rename — it breaks the live site and the publish
job's explicit table list at the moment of rename, for a naming benefit that arrives at cutover
anyway.

**SUPERSEDED: "rename `mart_*` → `fct_*` before Aug 27" (decided 2026-08-17).** That decision was
premised on the three tables being facts. They are not. Nothing needs to break before the season;
the migration is now gated on the dimensional layer existing, not on a date.

**Phase 1 model consequences:**
- `fct_game` — new, one row per game. `stg_games` already has exactly this grain, so it is a
  promotion with keys, not a build from scratch.
- `fct_game_team` — **split**: a normalized `fct_game_team` in `marts` (extended with
  `/games/teams` box scores), with the existing denormalized table becoming `srv_team_game_log`.
- `dim_team` — promote `stg_teams` to `marts` with a surrogate key, plus the `color`,
  `alternate_color` and `logos` columns sitting unused in raw. Season-scoped, not SCD2.
- `dim_conference` — genuinely new, small.
- `dim_provider` — `DraftKings` canonical; `Draft Kings` mapped to it in staging, with
  `provider_raw` preserved and a test that fails on an unmapped value.

---

## 2026-08-18 — Lines cadence: season-aware; Week 0 anchor resolved

**Week 0 open item (registered 2026-08-14) CLOSED.** Verified against NCAA.com and the ESPN
press release: the first games of the 2026 season are **Thursday 2026-08-27**, and they are
**FCS-only**; the first FBS slate is **2026-08-29** (UNC–TCU in Dublin, NC State at Virginia).
Sources label the window inconsistently — NCAA.com calls Aug 27 "Week 0" with Week 1 from Sep 5;
ESPN calls its Aug 28–30 broadcast slate Week 0. Both reconcile with the prior finding that
**CFBD treats 2026-08-27 → 2026-09-07 as Week 1**, a twelve-day two-Saturday window.

**DECIDED (Marc): lines cadence is configurable and season-aware** — daily off-season, every
4 hours from 7 days before the season's first game.

- **Window opens 2026-08-20** (7 days before the 2026-08-27 first game). The literal reading of
  the rule; using the first *FBS* game would give Aug 22. Kept the earlier date — two extra days
  of polling is trivial against an irreversible capture.
- **Window closes 2027-01-27.** CFP National Championship is **Monday 2027-01-25** at Allegiant
  Stadium, Las Vegas (confirmed on collegefootballplayoff.com and NCAA.com); +2 days because a
  7:30pm ET kickoff runs past midnight UTC and everything schedules in UTC.
- **Implementation: do not edit the schedule seasonally.** Schedule permanently at `0 */4 * * *`
  UTC and short-circuit outside the window so only the 00:00 run proceeds. Net effect is daily
  off-season and 4-hourly in-season, with no schedule change ever again. The gate must be a pure,
  unit-testable function and must **log its decision on every run including skips** — a silent
  short-circuit is indistinguishable from a broken DAG months later.

**SUPERSEDES: "betting lines monitored DAILY during game week" (Marc, 2026-08-14).** Daily
captures one point per day and permanently loses the intraday movement; Closing Line Value — the
fastest honest read on whether a model has edge — is uncomputable without it. Measured cost of the
change: ~180 extra API calls/month against a 75k tier, ~320 MB/season of raw growth.

**Also decided:** add a **load step to the snapshot DAG**, as a task separate from the fetch. The
DAG currently fetches without loading (loading happens only in the weekly DAGs), so the warehouse
can lag disk by a week. The raw files are the durable history, so only the *fetch* cadence is
irreversible — a load failure must never block the next fetch.

---

## 2026-08-18 — Three smaller decisions from the audit round

**`fct_team_record` keeps deriving from `stg_games`; `/records` becomes a reconciliation TEST,
not a source.** The live mart already computes W-L-T by unpivoting home/away, which is internally
consistent with the game spine. `/records` is landed and unused; a dbt test that diverges loudly
against it is cheap and is a stronger data-quality artifact than a source swap. Separately,
`tiebreak_rank` does not exist and must be added — CFBD has no standings endpoint, so conference
ordering is cfdb's own logic and the page must label it as such.

**Player page: ADD IT BACK to the wireframe.** Open since the first matrix. The economics changed:
`/plays` for 2024 is already landed (~570k rows) and the measured full 2024–2026 cost is ~1.0M
plays / ~0.87 GB / ~2 minutes of API time. `fct_play` and `fct_player_game_stat` now have a real
home rather than being mapped as interim tabs inside Stats, Team page and Matchup. Wireframe needs
a v0.3 revision.

**Open item registered — model surface vs upkeep.** Three layers over ~33 warehouse tables plus
18 serving views is a lot of surface for one person, against the project's own low-upkeep
constraint. The serving layer being views rather than tables keeps it tractable, but this is worth
watching rather than discovering in February. Revisit if Phase 2 starts feeling like maintenance
instead of building.

**Correction to the record:** `cfdb_page_to_mart_matrix_v2.xlsx` still describes a two-layer model
and a `mart_* → fct_*` rename. It is **wrong on both** as of this entry. The reconciliation report
and this log outrank it until it is regenerated.

## 2026-08-17 (later) — Layer separation DELIVERED and accepted

**All five work-order items verified and accepted** (commit `c6d404f`; Cowork spot-checked
the repo: schema configs, `generate_schema_name` override, and `ci/check_layering.py`
present as reported).
Highlights worth the record: both migrations were **metadata-only** (Postgres
`SET SCHEMA`; Unity Catalog cross-schema `RENAME` — 65 tables in 82 s, no 1.7 GB
deep-clone), checksum-verified data-neutral. Serving enforcement is real and **every
denial was tested, not assumed** (create/insert/drop all refused for `cfdb_read`;
`search_path = marts` keeps site SQL unchanged). The catch of the day: the site's
22-hour-old pooled connections predated the `search_path` change and would have silently
kept resolving to the now-empty `public` — deliberately restarted and re-verified against
live data. The CI layering guard was proven in both directions (passes clean; exits 1 on
a planted violation). The serving audit found nothing to remove — the publish job's
explicit mart list meant raw never could have shipped.
**Register updates:** the Databricks `files`-scope item is CLOSED — the Files API now
returns 200 on the same token; the 403 was scope propagation delay, not a missing scope
or Free Edition limit. `COPY INTO` is available for future loads.
**New open item:** publish-into-Airflow needs a **deploy-key decision** (how the publish
job authenticates/obtains code under Airflow). Claude Code to present options; Cowork
expects a read-only single-repo deploy key to be the shape of the answer, but the
decision is Marc's once options are on the table.
Freeze compliance noted: the transform-side schema moves landed 10 days before Aug 27,
per the sequencing rule attached to the decision.

## 2026-08-17 — Layer separation DECIDED: schema-per-layer + locked serving tier

**Context (Marc's review finding):** `raw_*` and `mart_*` tables are intermingled in one
namespace in Databricks — naming convention is the only thing separating layers, and
downstream consumers can see raw JSON-payload tables they should never touch.

**DECIDED (Marc): schema-per-layer in both engines, with real enforcement at serving.**
Work order for Claude Code:
1. **Databricks:** `raw` / `staging` / `marts` schemas under the catalog (dbt schema
   configs route models; loader writes only to `raw`). With one workspace user this is
   structural today; it makes Unity Catalog grants a one-liner when other principals
   appear.
2. **Transform Postgres:** same three schemas, replacing prefix-in-public.
3. **Serving Postgres (the enforced tier):** contains **published marts only** — raw and
   staging never ship to the droplet. The Streamlit app connects as a dedicated
   **read-only role with SELECT granted only on the marts schema** — the site becomes
   structurally incapable of reading upstream layers.
4. **dbt guard:** CI check that only staging models reference sources — no mart may
   select from raw directly.
5. **Audit:** verify what the provisioning publish actually shipped to the serving DB;
   if raw/staging tables landed there, remove them.
Sequencing note: transform-side schema moves touch the weekly pipeline's runtime path —
land them **before the Aug 27 freeze** or after Sep 7, per the standing freeze rule.
Serving-side lockdown is additive and freeze-safe anytime.

**Clarified (Marc's question): where dbt lives.** The project uses **dbt Core** (CLI, a
Python dependency in requirements.txt), not dbt Cloud — there is no hosted instance and
no separate dbt credential. Connections come from `dbt/profiles.yml` (gitignored),
which reads the already-provided Postgres creds and `DATABRICKS_HOST`/`DATABRICKS_TOKEN`.
Execution: locally via CLI, and inside the Airflow image where every weekly DAG runs
`dbt run → dbt test` as tasks. dbt Cloud adds nothing here (Airflow owns scheduling);
`dbt docs generate` provides the lineage view on demand.

## 2026-08-16 (late night) — Serving stack LIVE at <site-host>

**The hosted stack is live and locked:** droplet (SFO, $6) running serving Postgres +
Streamlit + cloudflared via Compose; tunnel Healthy; `<site-host>` behind
Cloudflare Access with One-time PIN and the `friends-and-family` email-allowlist policy.
Marc completed the full Cloudflare manual setup (tunnel, token, published application
route, Access application) and verified the allowed-email login end-to-end. **Stranger
test PASSED 2026-08-16** (non-allowlisted email refused) — edge auth fully verified,
both directions.
**Setup findings worth keeping:** (1) Cloudflare made its own "Cloudflare" IdP the
default for new Zero Trust accounts (changelog 2026-06-18) — One-time PIN must be added
manually under Zero Trust → Integrations → Identity providers, and the app pinned to it;
(2) by documented design, Access only sends the PIN email when the address matches an
Allow policy, while the login page always claims a code was sent — so "no email arrived"
means policy mismatch, not mail failure; PIN sender is noreply@notify.cloudflare.com
(tell guests to allowlist it); (3) the public-hostname route lives under the tunnel's
"Published application routes" tab in the current UI, distinct from private hostname
routes (which require the One Client and are not for this site).
Architecture note: this completes the edge-auth design exactly as specified in CLAUDE.md
— no auth code in the app, strangers stopped at Cloudflare's edge, ≤50 users free.

## 2026-08-16 (night) — Hosting DECIDED: DigitalOcean droplet, $6/month

**DECIDED (Marc): the serving layer + site host on a DigitalOcean Basic droplet — $6/mo
(1 GiB / 25 GiB SSD), SFO region.** Design: Docker Compose mirroring the local stack —
serving Postgres + Streamlit + Cloudflare Tunnel — with Cloudflare Access (free ≤50
users) in front, per the settled access-control architecture. No open inbound ports;
auth at the edge; no auth code in the app.
Why over the alternatives (researched 2026-08-16, current prices): Hetzner's cheaper EU
tiers (~€4) put ~150 ms of transatlantic latency under a websocket-heavy app served to a
California audience; the $0 stack (Neon free + Streamlit Community Cloud) carries a
0.5 GB storage ceiling, cold starts on both layers, and — decisive — cannot sit behind
Cloudflare Access, silently reversing a settled decision. DO at $6 is the only option
with no structural compromise; upgrade path to $12/2 GiB is one reboot if memory
pressure appears.
**Cost ledger from here:** droplet $6/mo + domain (~$10/yr ≈ $0.83/mo) ≈ **$7/mo total
recurring**, against the $0–15 guardrail. First recurring spend in the project.
**Manual items (Marc):** create the DO account + droplet; pick/register a domain and add
the zone to Cloudflare (Access + Tunnel hang off it). **Claude Code:** provisioning
compose/tunnel config, publish job wiring, serving-db backup scheme (register item).

## 2026-08-16 (later) — M4 step 2 accepted; M5/M6 UNBLOCKED from M4; site work starts now

**Accepted: M4 step 2 (Databricks target + parity).** Verification was measured, not
asserted: md5-identical staging output, multiset-identical mart rows for 1900 + 2024
(exercising the date-only era logic on Spark), 51/51 dbt build on the warehouse. The two
documented false-positive traps (locale vs codepoint collation; t/f vs true/false boolean
rendering) are noted with approval — both were measurement errors caught before they were
reported as data bugs. Cutover (step 3) correctly deferred as freeze-protected.

**DECIDED (Marc): M5 and M6 unblock from M4 — the site cannot wait for Sep 7.** The
presentation layer is the heavy lift and needs production-shaped marts now. Cowork's
architectural basis for why this is safe: the site's contract is marts-in-Postgres, and
the step-2 parity evidence proves mart contents are engine-equivalent — so the Databricks
cutover changes the producer, invisibly to the consumer. Sequencing: (a) M6 development
starts immediately, locally, against existing marts; (b) hosting research (Cowork)
happens now, recommendation ASAP; (c) M5 publish job is additive and freeze-safe,
sourcing from transform Postgres until cutover, then from Databricks — same contract.
(d) M4 step 3 timing unchanged: after Sep 7, backed by shadow-run parity through the
freeze. Full raw load to Databricks (volume + COPY INTO) proceeds now — additive.

**Boundary reminder recorded with the unblock:** no metric computation in Streamlit —
site-needed numbers become dbt marts via the demand-driven process, even under schedule
pressure. The pressure to ship visuals is exactly when that rule earns its keep.

## 2026-08-16 — M2b delivery ACCEPTED

**Cowork review of the M2b delivery (commit `58f3816` → PR #4): all three exit criteria
verified against the repo and accepted.**
(1) *2026 framework:* audit-first honored — only true gaps pulled (2026 teams/roster/
coaches/conferences + schedule re-pull); the any-team-any-week acceptance query is live.
(2) *Curated history:* `history` + `min_season` declared in the registry, floors probed
against the API (games/records 1869, coaches 1886, rankings 1936, draft 1967, advanced
2001, player stats 2004, wepa 2008, ppa 2013); 1,238 requests / 156 seasons / zero
failures; two guard tests keep the ratified set and the sweep bound to this log.
(3) *Analyst models:* `mart_team_schedule` (220,204 team-games incl. 2026 futures) and
`mart_team_season_record` (30,221 team-seasons, 1869–2025); repo CLAUDE.md synced.
**Commended:** the date-only timezone bug — 66,496 pre-2001 games (60% of all games ever)
would have shifted back a day; caught, fixed with per-season era detection,
regression-tested, and spot-verified against known history back to Rutgers–Princeton 1869.
This is the data-quality discipline the project exists to demonstrate, operating at full
depth. Also noted: PR #4 merged all outstanding work to `main`, closing the
unmerged-branch punch item.
**Residual — ✅ closed 2026-08-16:** Marc inspected Oklahoma State's data and it passed.
M2b acceptance is complete on both the mechanical and human sides; nothing remains open
on this milestone.

## 2026-08-16 — M4 unblocked; pre-season hardening endorsed; validation check-ins set

**DECIDED (Marc): M4 runs in parallel with M3's validation window.** Claude Code correctly
observed that M3's remaining requirement is time passing, not work — blocking M4 on a
calendar event bought no risk reduction. Cowork's added guardrail, accepted with the
decision: M4 is sequenced so the validation stays unambiguous — macro layer first (M2b
models born dialect-neutral, resolving the JSON-unnesting register item), existing-model
refactor lands **before Aug 24**, and a **weekly-path change freeze Aug 27 – Sep 7**
(fixes excepted; purely additive Databricks work unconstrained). A Sep 7 failure must be
unambiguous about what failed.

**Endorsed, effective now (no new decision needed — all within existing remit):**
postseason `seasonType` hardcode fixed before unattended runs begin, not "before
December"; dbt tests added to CI (Postgres service container) before Aug 27;
`src/ingest_stub.py` deleted. All three were Claude Code's recommendation; Cowork concurs
and re-dated its own register entries accordingly.

**Accepted: the `calendar` full-history amendment** (entry below) — the one-registry-line
+ one-log-line path worked as designed, and the CI membership guard makes the ratified set
enforceable. The measured floors table (2001 kickoff times / 2002 week boundaries / 2004
player stats) is exactly the kind of record that saves a future re-probe.

**Scheduled:** Cowork validation check-ins on **Aug 30** (first genuine unattended Sunday
run — the day alerting proves itself) and **Sep 7** (Week 1 closes; M3 evaluated for
close-out). Note: the Sep 8 Tuesday sweep catches Labor Day Monday games; the Sep 7 review
will account for that when judging cycle completeness.

**Still owed by Cowork:** review of the M2b delivery (2026 framework, curated history,
first analyst models) — built and pushed, acceptance not yet recorded.

## 2026-08-15 (early morning) — Amendment: `calendar` joins the full-history set

**DECIDED (Marc): `calendar` is added to the ratified full-history endpoint set**, taking
it from 11 endpoints to 12.

**Floor: 2002.** Probed against the live API rather than assumed, per the practice
established with the original set — CFBD serves no calendar at all before 2002. Landed:
25 seasons (2002–2026), 22 fetched, zero failures.

**Why this one earns its place.** The calendar is not analytical data; it is the thing that
tells the pipeline what a "week" *is*. Week enumeration in `src/snapshot.py` and
`src/weekly.py` derives week boundaries from it rather than from a hardcoded count,
precisely because season length varies (2024 had 16 regular weeks, 2026 has 15). Holding it
at 2024+ meant any future week-level work on an older season would have had no week
boundaries to use. This removes that constraint before it becomes a blocker rather than
after.

**Three floors now bound how deep week-level analysis can go**, all measured rather than
assumed, and worth keeping together:

| Floor | What becomes available |
|---|---|
| 2001 | Kickoff times — before this, CFBD stores date-only values at midnight UTC |
| 2002 | Week boundaries (this amendment) |
| 2004 | Player-season statistics |

If play-by-play depth beyond 2024 is ever proposed, those are the real bounds on it. No
decision implied here — recorded so the question can be answered without re-probing.

**Process note: the amendment path worked as designed.** One registry line in
`src/endpoints.py`, one entry here. The registry's ratified set is additionally guarded by
`test_the_ratified_full_history_set_is_exactly_what_was_decided`, which fails CI if
membership drifts from this log — so the list cannot quietly grow without a decision being
recorded. That guard is what makes "one line plus one line" enforceable rather than
aspirational.

**Not covered by this entry:** M2b delivery itself (2026 framework, the original curated
history, and the first analyst models) is built and pushed but remains unreviewed. Its
acceptance is Cowork's to record after review, not Claude Code's to assert.

## 2026-08-15 (late night) — Data horizon expanded: M2b work order

**Context:** Marc has begun analyzing the data directly, ahead of the site — the first
real demand on the demand-driven modeling policy. Two horizons were missing.

**DECIDED (Marc): the 2026 season framework lands now, before Week 1.** Schedule, rosters,
coaches, preseason rankings, season-scoped teams — the season is on the calendar and its
structure must be queryable today, even where plays/drives/lines don't exist yet.
Acceptance: any team's 2026 schedule, week by week, from Postgres.

**DECIDED (Marc): full API-depth history for a curated set of season-level endpoints —
not for everything.** The ratified set (~a dozen): games, records, rankings, teams,
coaches, stats/season, stats/season/advanced, stats/player/season, wepa/team/season,
ppa/players/season, plus `draft/*` (added at Marc's direction). Each endpoint's own
availability bounds its depth. Everything else stays 2024+; PBP/drives/lines and per-game
fan-outs unchanged. This resolves CLAUDE.md's long-standing "depth TBD per feature" —
CLAUDE.md amended accordingly. Implementation: a declarative `history` attribute in the
endpoint registry, so depth stays auditable and amendments are one line + one log entry.

**DECIDED (Marc): first analyst models get built** — a schedule mart (any team, any week,
any season incl. 2026) and `mart_team_season_record` extended over the new history. This
is demand-driven modeling passing its first live test, not a policy change.

**Roadmap impact: none to existing milestones.** Recorded as M2b, riding the existing
registry + backfill machinery; no DAG changes; M3 validation, M4, and all gates unmoved.
Budget: a few thousand `season`-strategy calls vs 75k monthly quota.

## 2026-08-15 (night) — Cowork review of M2 + M3

**M2 (historical backfill): COMPLETE and accepted.** 2024–25 landed across the full
sweepable surface (1.3M rows, zero failures, idempotent rerun), season-scoped team
dimension implemented — the `stg_teams` register item is hereby ratified.

**M3 (weekly pipeline): BUILT AND SHAKEN OUT — not yet "complete."** The distinction is
the review's core finding: the exit criterion "a full cycle completes unattended against
Week 1" cannot be satisfied before Week 1 exists. First slate 8/27–29; **M3 closes when
the Sep 7 unattended cycle completes clean.** Recorded as 🔶 pending, not ✅, because the
audit trail's value is that its checkmarks mean what they say.
Build quality assessed as excellent: registry-driven DAGs (no drift between cadence
decisions and runtime), correct Airflow/dbt boundary (failing dbt tests fail the run),
`catchup=False` with sound reasoning in both DAGs, week-scoped lines snapshots already
capturing pre-opener movement (the 8/24 constraint is met early), never-raise two-channel
alerting with self-test tooling, and a freshness/empty-response layer that closed a real
silent-failure mode the shakeout itself exposed (17 of 23 endpoints empty-200 under a
green DAG). Fernet-key carry-over resolved properly.
**Pre-validation punch list (Claude Code + Marc):** (1) configure and test SMTP alerting —
`python -m src.alerting --check` then `--test`; a failure log nobody reads isn't alerting;
(2) merge `m2/historical-backfill` → `main` via PR — M2 and M3 both live unmerged, and
PR-by-convention is the project's substitute for branch protection.
**New register items:** postseason `seasonType: regular` hardcode in the weekly refresh
(fix before December); Airflow's all-admins local auth accepted as local-dev-only posture,
must be revisited if the stack ever binds beyond localhost.

## 2026-08-15 (later) — Endpoint scope REVERSED: capture-maximal; per-game fan-out skipped

**REVERSAL (Marc): raw capture goes from site-pulled to maximal.** Marc directed Claude
Code to sweep the full breadth of CFBD endpoints for maximum analytic and reporting
capability, reversing M1's ratified "scope is pulled by what the site needs" and rescinding
the out-of-scope list (`/draft/*`, `/recruiting/*`, `/player/portal`, `/talent` — all now
swept). This is recorded as a reversal, not a reinterpretation.
Why it's sound: measured cost removed the original constraint's teeth — the full two-season
sweep of 63 endpoints cost 332 calls (0.5% of monthly quota), 1.0 GB raw, 180 MB Postgres,
1.3M rows, zero failures. You can't analyze data you didn't land, and landing it is nearly
free. The demand-driven principle moves down a layer instead of dying: **dbt models are
built only for what the site or a concrete analysis consumes** (64 raw tables will never
mean 64 models), and expensive fan-outs face the same test (below).
Accepted with it: the declarative endpoint registry (`src/endpoints.py` — path, strategy,
cadence bucket) becomes the operative cadence source of truth; the roadmap appendix is
rationale, not runtime config. Also noted with approval: three registry misclassifications
were diagnosed from 400 bodies stored in raw — the immutability rule working as intended.

**DECIDED (Marc): per-game fan-out SKIPPED for now.** `/game/box/advanced` and
`/metrics/wp` (~15k calls ≈ 20% of monthly quota for 2024–25) stay built and opt-in behind
`--per-game`, unrun until a concrete analysis or site feature demands them. This draws the
scope line where it now lives: sweepable = capture-maximal; fan-out = demand-driven.

**Registered open:** which staging/marts to build beyond teams+games — demand-driven,
pulled by M6 site features or a specific analysis. Owner: Cowork.

## 2026-08-15 — Week-0 findings reviewed; weekly schedule decided

**Cowork review of Claude Code's roadmap updates: verified and accepted.** The Week 0
closure method (proving against 2024 warehouse data that CFBD folds the early Saturday into
`week = 1`) is sound; the `/plays` volume study's arithmetic checks out (~21k plays / 18 MB
per sampled week → ~1.0M plays / 0.87 GB / ~2 min fetch across 3 seasons — no
backoff/resumability machinery warranted, disk is the watch item). The two corrections are
accepted as recorded: `/games` is authoritative for dates (`/calendar` is FBS-oriented),
and CFBD Week 1 2026 is a twelve-day, two-Saturday window (2026-08-27 → 2026-09-07).

**DECIDED (Marc, 2026-08-15): weekly results refresh anchors to fixed calendar days —
Sunday morning + Tuesday morning sweep.** Sunday captures the Thu–Sat slate fresh; Tuesday
catches Monday games (Labor Day week) and early stat corrections. Rejected: per-CFBD-week
triggering, which would leave the Aug 29 FBS opening slate unpulled until Sep 7. Either
day's stragglers are covered by C2's prior-week re-pull, so the choice traded freshness,
not correctness.

**Clarified:** the pipeline *captures* every division `/games` returns (already the
ratified C1 design); what the *site displays* (FBS-only vs broader) is an M6 presentation
choice, deferred. The 2026-08-24 daily-lines deadline is accepted as the binding
constraint — Claude Code should stand up the minimal scheduling path (incl. the Fernet-key
carry-over) ahead of full M3 validation.

## 2026-08-14 (night) — Roadmap adopted; M1 ratified with amendments

**`roadmap.md` adopted as the single milestone list** (drafted by Claude Code, reviewed and
amended by Cowork same day). Supersedes the three parallel numbering schemes; `claude_code/project_setup_actions.md` retired to `claude_work/archive/`.

**M1 (endpoint scope + cadence) ratified ahead of its 2026-08-20 gate, with amendments:**
- *Bucket C split into C1/C2.* Revisionist data (ratings, cumulative stats) keeps full-season weekly re-pull; immutable-once-complete data (`/plays`, `/drives`, box scores) pulls current + prior week only — Bucket B's immutability logic applies within a season, and the prior-week re-pull absorbs stat corrections. Staging dedup for C2 becomes per (season, week).
- **Betting lines (Marc): in scope, displayed, monitored DAILY during game week.** Rationale: line movement is itself the signal — action shifting to/from a team, or a major injury/player issue. Design consequence: `/lines` staging keeps *every* snapshot (no latest-only dedup); movement across snapshots is first-class mart material (open → current → close). Adds a daily schedule to M3's Airflow work, the only daily cadence in the system. Terms posture unchanged: display yes, redistribution no; context, not a betting product.

**Corrections/adjustments from roadmap review:** M0 wording fixed (Databricks `dbt debug` stretch criterion moves to M4 — it never ran in phase 1); M3 unserialized from M2 (DAG development proceeds in parallel; only final unattended validation needs the backfill).

**New open items registered:** (1) *Week 0* — Claude Code verifies whether the 2026 CFBD calendar has a Week 0 slate on 2026-08-22; if so, Cowork decides whether the weekly streak starts there (moves M3's real deadline in by a week). (2) *Serving/hosting* — where always-on Postgres + Streamlit live and what it costs against the $0–15/mo guardrail; decide before M5 starts. First recurring spend in the project; Cloudflare Access setup comes due at the same time.

## 2026-08-14 (evening) — Cowork review: CI workflow + dbt spike

**CI workflow (`.github/workflows/ci.yml` on `main`): approved as-is.**
Lint + offline pytest on every PR/push (tests stub all network calls — no rate-limit spend, no key needed); CFBD live smoke test isolated to a manual `workflow_dispatch` job, which doubles as the acceptance test for the `CFBD_API_KEY` secret; CI steps enforce two governance constraints mechanically (no secret-shaped files tracked, no `data/` tracked — the CFBD no-redistribution rule as a failing check); raw data deliberately not uploaded as an artifact. Minor/no-action: `PG_*` secrets and dbt not referenced by CI yet (expected in phase 1).
*Correction for the record:* Cowork initially flagged `actions/checkout@v7` / `setup-python@v7` as nonexistent based on a bad web summary; verified against the actions repos' git tags that **v7 exists for both**. No blocker; the flag was wrong, not the workflow.

**Branch protection on `main`: resolved as N/A.**
Verified against GitHub docs 2026-08-14: protection rules and rulesets on private repos require Pro+; Free supports them on public repos only. Skipped per the $0–15/mo guardrail. PR workflow holds by convention + CI; revisit if the repo goes public or gains collaborators.

**dbt spike (`spike/dbt-raw-to-marts`): strong; architecture question resolved below.**
What's good: staging enforces quality rules in the right layer (filters non-200 fetches, dedups to latest file per season), sources are declared immutable with tests, the mart declares its grain via `team_season_key` + unique test, and two singular reconciliation tests implement rule #4 (W+L+T = games played; league-wide wins = losses per season — the latter catches one-sided/duplicated game counting). Raw filename timestamp fix (`fix/raw-filename-timestamp`) is correct and regression-tested; filenames are the manifest/load key, and lexical sort now works cleanly.
Flags for Claude Code: (1) the mart's `relationships` test (team_id → stg_teams) may conflict with the acknowledged reality that non-FBS opponents appear in games but possibly not in the teams list — confirm `dbt test` passes on real 2024 data; (2) the staging SQL is Postgres-specific (`jsonb_array_elements`, `distinct on`, `filter`) and will need rewriting for Databricks — keep it isolated in staging and don't let the dialect spread.
**DECIDED (Marc, 2026-08-14): Postgres-first dbt blessed as spike-only, with an explicit expiry.**
Context: the spike runs dbt against local Compose Postgres (`dbt-postgres` added to requirements), while settled architecture has transforms on Databricks and Postgres as read-only serving. Decision: Postgres stays the dbt target while the model shape is iterated — a prototyping convenience, not an architecture change. Expiry condition: a Databricks target must be added and become the primary transform target **before any mart feeds anything user-facing**. Corollary for Claude Code: keep Postgres-dialect JSON SQL confined to staging so the migration surface stays small, and treat the Databricks target as due sooner rather than later — dialect-specific SQL compounds with every model added.

## 2026-08-14 — Project setup round (from claude_code/project_setup_actions.md)

**GitHub repo name: `ncaa_football` (private).**
Why: the repo name should describe the project, not the tooling. The originally proposed `claude_code` is a tool name and reads poorly on a portfolio GitHub. Local folder names (`claude_work`, `claude_code`) are unchanged — repo name and folder name don't need to match.

**Databricks Free Edition: set up now, not deferred.**
Why: it's the settled warehouse anyway; setting up the account now avoids a later dbt target migration. Verified 2026-08-14 that Free Edition is active (docs last updated Jul 2026): serverless-only, one workspace/metastore, one 2X-Small SQL warehouse, max 5 concurrent job tasks, one active pipeline per type, non-commercial use only. All compatible with this project's weekly-batch, private-site scope. Signup: https://signup.databricks.com/

**Setup tracking: markdown checklist in `claude_work` (see `setup_checklist.md`), not GitHub Issues/board.**
Why: solo project; a board is overhead without an audience. The decision log + checklist serve the same audit/interview purpose.

**Cowork sign-offs requested by project_setup_actions.md — confirmed:**
- Postgres for dev/CI runs via Docker Compose (no separately provisioned instance in phase 1). Already settled in CLAUDE.md.
- Airflow in Docker via `docker-compose.airflow.yml` is acceptable. Already settled in CLAUDE.md.
- CFBD terms: caching/storing data and displaying it on the private site is allowed; no redistribution or mirror API; API key server-side only. Reviewed previously; constraints recorded in CLAUDE.md.
- Cloudflare Access credential storage: deferred — no site deployed yet; revisit when the site leaves local dev.

## 2026-08-14 — Working context moved

Cowork context folder moved from `automagical/cfdb` (deleted) to `ncaa_football/claude_work`. Code repo lives at `ncaa_football/claude_code`, scaffolded with its own CLAUDE.md. The claude_work CLAUDE.md's division-of-labor table was updated accordingly.

## Earlier (Aug 2026, pre-log)

Architecture, data scope, division of labor, cost guardrails, and CFBD compliance constraints settled — recorded in `CLAUDE.md`, which remains the source of truth for *what and why*.
