"""Methodology — page 18. How every number on this site is produced.

The only page in cfdb that reads no serving view, because its subject is the pipeline rather
than the data. It is also the page that makes the rest of the site auditable: a figure whose
derivation is written down can be argued with, and a figure whose derivation is not is just
an assertion with a decimal point.

Everything here is stated as it is actually implemented. Where cfdb does something the
reader would not expect — an away-minus-home margin, a model that refuses to forecast before
Week 5 — this page says so plainly rather than letting the surprise arrive on a table.
"""
import streamlit as st

from lib import shell


def body(page) -> None:
    st.markdown("""
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

### The sign convention, which is not the intuitive one

Margins are stored **away points minus home points**.

- A **negative margin** means the **home team won**.
- A **negative spread** means the **home team was favoured**.

This is inherited from the modelling pack rather than chosen, and it is preserved untouched
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
