"""Methodology — page 18. How every number on this site is produced.

The only page in cfdb that reads no serving view, because its subject is the pipeline rather
than the data. It is also the page that makes the rest of the site auditable: a figure whose
derivation is written down can be argued with, and a figure whose derivation is not is just
an assertion with a decimal point.

Everything here is stated as it is actually implemented. Where cfdb does something the
reader would not expect — an away-minus-home margin, a model that refuses to forecast before
Week 5 — this page says so plainly rather than letting the surprise arrive on a table.

🚨 EVERY NUMBER ON THIS PAGE IS A LIABILITY, AND A233 CHOSE HOW THEY STAY TRUE.

**Dated literals, guarded by a test.** `SCALE_AS_OF` dates them and
`tests/test_methodology_figures.py` re-measures every one against the repository — the dbt
manifest, the endpoint registry, the page registry, pytest's own collection. A change that
makes a figure wrong fails CI rather than sitting here looking authoritative.

⚠️ THE DATE AND THE TEST DO DIFFERENT JOBS AND BOTH ARE NEEDED. The test keeps the number
TRUE; the date keeps it HONEST for the reader, who cannot see the test and is entitled to
know the count was taken at a moment rather than computed as they look at it.

⚠️ THE TWO ALTERNATIVES WERE PRICED AND REJECTED (A233, cfdb-main-R-3114):

  generated at build time — a script writing counts into a file the page reads. It adds a
      place it must run, a staleness question of its own, and an "what does the page show
      when the file is missing" state. **The test already forces the update, so the
      generation buys nothing the literal does not have.**

  read from serving — barred twice over. §4.2.1 forbids counting in the app, so a count
      would have to be a COLUMN on a serving view, which is a dbt round; and this is the one
      page that deliberately reads NO serving view. Making it read one to print its own size
      is a design change, not a detail.

⚠️ AND THE TEST-SUITE FIGURE IS DELIBERATELY A FLOOR RATHER THAN AN EXACT COUNT. An exact
number would be wrong the moment anybody adds a test — which is every round — so the page
says "more than" and the guard asserts the floor. A figure that forces a page edit on every
unrelated round is a figure that will eventually be edited without being re-measured.
"""
import streamlit as st

from lib import shell

# 📊 THE DATE THESE COUNTS WERE TAKEN. Printed on the page, so a reader can see how old the
# shape of the project is rather than having to trust that it is current.
SCALE_AS_OF = "September 2026"


def body(page) -> None:
    st.markdown(f"""
### What this is, in numbers

As of {SCALE_AS_OF}, and re-measured against the repository by a test rather than typed here
from memory:

| | |
|---|---|
| CFBD endpoints in the ingestion registry | **84**, of which **61** are fetched on a cadence |
| dbt models | **175** — **81** staging, **58** dimensional, **36** serving |
| dbt data tests | **650** — **510** schema tests and **140** hand-written assertions |
| Python tests | more than **2,250** |
| Pages on this site | **18** |
| Serving columns, every one with a written definition | **1,502** |
| Databases | **two** — a warehouse where everything is built, and a small serving Postgres the site reads |

The two databases are the point of the shape rather than an accident of it. The site never
queries the warehouse, so a page cannot be slowed down by a rebuild and a rebuild cannot be
slowed down by a reader.

### Where the data comes from

Every fact on this site originates from [CollegeFootballData.com](https://collegefootballdata.com),
fetched through their API and landed unmodified. The raw layer stores each API response
exactly as it arrived, including the failures — a request that returned 401 is kept as a 401
rather than dropped, because an endpoint that stopped answering is information.

Nothing is hand-entered, and nothing is corrected by hand. Where a source value is wrong, it
stays wrong and the discrepancy is reported rather than quietly patched, so that this site
and CFBD can always be reconciled.

### How it is transformed

Three layers, each with one job, enforced by a check that reads the compiled dependency
graph rather than trusting anybody's discipline:

| Layer | Prefix | What it does |
|---|---|---|
| Staging | `stg_` | Unpacks JSON, filters failed responses, deduplicates. One model per endpoint. |
| Dimensional | `dim_` / `fct_` | Conformed keys, business definitions, tests. Every metric is defined exactly once. |
| Serving | `srv_` | Pre-joined wide tables the site reads. No logic, only shape. |

The site itself is display-only. It issues single-table selects against the serving layer
with filters and nothing else — no joins, no arithmetic, no metric definitions. That is a
constraint checked in code on every query, not a convention: if a page needs two things side
by side, that is a change to a serving view, not a change to a page.

### When a number here changes and no game was played

CFBD revises its own history. Comparing a fetch from August against one from September, the
provider had restated predicted-points-added across **6,250 team-game records** in the 2024
and 2025 seasons — 95.8% of the records in that endpoint — while other endpoints in the same
family had not moved at all.

cfdb refetches those seasons and republishes them, so this site follows the source rather
than freezing whatever it happened to see first. **The raw layer is append-only**: the August
payload and the September one are both kept, so any change is reconstructable rather than
merely asserted. A figure you read here in August may therefore differ in September, and the
freshness stamp on every page is when cfdb last built it.


### How it gets here, and what happens when it is wrong

A scheduled pipeline runs the whole chain — fetch, load, build, test, publish — on cadences
that differ by domain, because a betting line and a final score go stale at different rates.
Scores refresh every two hours during a slate; betting lines every four; the weekly
rebuilds run after the games are final.

**The publish is gated on its own tests.** If an assertion fails, the publish does not run,
and the site keeps yesterday's data with yesterday's timestamp on it. That is the deliberate
trade: a reader gets a number that is a day old and says so, rather than a number produced by
a build that failed its checks. It costs freshness and it buys the thing freshness is for.

**A dead-man's switch watches from outside.** It runs on different infrastructure from the
pipeline and alerts when a heartbeat stops arriving, because a monitor that shares fate with
the thing it monitors is not a monitor — a stack that is down cannot report that it is down.

**And since September 2026, a check refuses to merge new work while the publish path is red.**
The rule existed before that as a written one and was broken three times, including once by
the person who wrote it. A rule that depends on remembering is not a control.


### What it runs on

The whole of it — the ingestion, the warehouse, the transformation layer, the scheduler and this
site — runs on modest hardware for **under $15 a month**. The two-database shape above is part of
why: the site reads a small Postgres holding only what has been published, so serving a page costs
almost nothing, and the expensive work happens on a schedule rather than while someone is looking.

### Every column the site reads has a definition, and the definition travels

Every column in the serving layer — the **1,502** columns this site reads — carries a written
definition. Those definitions are not kept in a document beside the code; they are attached to the
columns themselves when each table is built, read back out of the database, and published like any
other data.

They reach you two ways. The **Data Dictionary** page lists them, filterable by table. And every
Excel export carries a **Data Dictionary** as its second sheet, generated from the same view the
page reads, so the workbook and the site cannot disagree about what a field means. That sheet also
names which sheet each field appears on, and leaves it blank where a field is documented but not
exported — documented and shipped are different claims, and the sheet says which is which.

### When this page changes

When a round changes it. This is prose, and prose is only as current as the last person who read
it — which is why the counts above carry a date.

The counts themselves are not typed from memory. Most of them — the endpoints, the models, the
tests, the pages — are re-measured against the repository by a test that fails the build when one
drifts, so those can only be stale if nobody has built since, and the build runs on every change.

The count of documented columns is checked differently, because it is a fact about the database
rather than about the repository: the definitions live on the columns themselves, so the test reads
them from the live database. That check runs for anyone who can reach it, and not in the build.

### The sign convention, which is not the intuitive one

Margins are stored **away points minus home points**.

- A **negative margin** means the **home team won**.
- A **negative spread** means the **home team was favored**.

This is inherited from the modeling pack rather than chosen, and it is preserved untouched
through every layer. Flipping it midway would invert every cover flag, every edge and every
against-the-spread record while continuing to look entirely plausible — so it travels intact,
and where a page shows a home-perspective figure it reads a separately named column that dbt
computed, never a sign the page flipped itself.

Verified against all 5,133 training rows: home teams win 74.4% of games with a negative
spread and 31.4% of games with a positive one.

### Implied probability and the bookmaker's margin

Moneylines are converted to probabilities and then **de-vigged multiplicatively**: each side's
raw implied probability is divided by the sum of both. A book pricing both sides at −110
implies 52.4% each, totalling 104.8%; the 4.8% is the book's margin, and removing it is what
makes the two numbers comparable with a model's.

Raw prices are never altered. The de-vigged figures are additional columns, the method used
is stored beside them, and the overround is shown so the size of the adjustment is visible.

### What the model is, and what it is not

Predictions are cfdb's own, produced by models trained using a commercially licensed training
pack. **They are not CollegeFootballData.com predictions**, and CFBD does not endorse them.
That attribution is carried as a data column on every serving view containing a prediction,
so a page physically cannot display the numbers without having fetched the statement.

**Model predictions begin in Week 5 of each season.** The models need several weeks of the
current season's results before they can forecast the current season's teams, so Weeks 1 to 4
have no predictions at all. That is by design and it recurs every year. Pages that depend on
predictions render as empty during those weeks and say why, rather than showing a placeholder
that would imply an opinion the model does not have.

Accuracy figures published on Model Performance are **held-out backtests, not realised
betting results**. Nothing on this site has been bet. A backtest hit rate and a realised hit
rate are different claims and are never styled alike.

### The models this site stopped publishing

Most of them. Of the seven models cfdb had trained, **six were found to have been given the
closing spread as an input and then scored on how well they beat that same spread.** Their
accuracy figures described a model that had already seen the answer.

They were withdrawn rather than published with a caveat. One model remains — the one whose
features contain no market data of any kind — and the Model Performance page names the
withdrawn ones and why, rather than quietly becoming a shorter table.

**Nothing was deleted.** The predictions are still in the warehouse; the site stopped
presenting them as results. A replacement trained without any market input is being built.

This is on the Methodology page because it is the part worth reading. The withdrawn figures
were the most impressive numbers this site ever showed, and they were impressive because the
models were shown the thing they were being graded against. **Finding that in your own work
is the job; the leaderboard was the easy part.**

### Nothing here is betting advice

cfdb is a portfolio project about data engineering. It reports where a model and a market
disagree; it does not tell anyone to act on that, and a measured edge is not an expectation
of profit.

### How freshness is reported

Every page states when its own data was loaded, taken from a column rather than from the
clock in your browser. Freshness is tracked per domain, because a betting line and a 1936
poll have very different notions of recent. Where a section's source has not been built yet,
the page names the missing object rather than rendering an empty table — an absence and a
zero are different answers.
    """)


def render() -> None:
    shell.render_page("methodology", body)
