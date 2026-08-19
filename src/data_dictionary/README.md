# Data dictionary

What each CFBD endpoint represents, what its grain is, and what every field means.

```bash
python -m src.data_dictionary                    # uses config/api-docs.json and data/raw
python -m src.data_dictionary --out /tmp/dd.xlsx --profile-out /tmp/profile.json
```

## Why this exists

CFBD's OpenAPI spec is complete on structure and almost silent on meaning. Measured against
v5.24.0: **1,017 response fields, four of which carry a description.** Endpoint descriptions
and query-parameter descriptions are good and complete; field meaning is published nowhere
except the 22 concepts in [CFBD's glossary](https://collegefootballdata.com/Glossary).

Grain is worse — the spec never states it. Nothing tells you that `/games` is one row per game
while `/games/teams` is one row per game with the team split nested inside it. That has to be
measured.

So the dictionary is assembled from three sources and **labels every definition with which one
it came from**:

| Provenance | Meaning | Authoritative? |
|---|---|---|
| `glossary` | CFBD's published definition, verbatim | yes |
| `docs` | CFBD's text in the OpenAPI spec | yes |
| `spec` | structural fact — type, nullability, enum | yes |
| `observed` | measured from `data/raw` | yes, about the sample profiled |
| `inferred` | ours | **no** — check the confidence |

Inferred rows carry `high` / `medium` / `low` confidence. This separation is the whole point.
A previous workbook in this project was wrong for weeks without anyone noticing, because
nothing on its face distinguished a measured fact from a guess.

## Layout

| File | Role |
|---|---|
| `definitions.json` | **the definition map.** Data, not code — edit it directly |
| `definitions.py` | loads the map; `define()` applies the provenance rule |
| `spec.py` | flattens the OpenAPI document to endpoint / field / parameter rows |
| `profile.py` | measures `data/raw`: grain, null rates, value domains |
| `workbook.py` | renders the xlsx |
| `__main__.py` | CLI; computes the Gaps sheet |

## Editing definitions

Everything lives in `definitions.json`.

- `glossary` — CFBD's words. **Quote, never reword.** Changing this is falsifying a source.
- `glossary_fields` — field name → glossary term. Only map a field here when its **unit
  matches the term**. `havocRate` is a percentage and maps to Havoc; `totalHavocEvents` is a
  count and must not. Count-vs-rate confusion produces a definition that reads perfectly and
  is wrong, so `tests/test_data_dictionary.py` pins the known cases.
- `canon` — field name → `[definition, confidence]`. Keys are lowercased leaf names, matched
  against the last segment of a dot-path, so defining `school` covers `teams[].school` too.
- `patterns` — ordered prefix/suffix fallbacks. Keep this short; a pattern that fires widely
  produces vague definitions everywhere. Anything reaching the end is marked `low`.

A field must not appear in both `glossary_fields` and `canon` — a test enforces it.

## Refreshing

```bash
curl -o config/api-docs.json https://apinext.collegefootballdata.com/api-docs.json
git diff config/api-docs.json     # a reviewable record of what CFBD changed
python -m src.data_dictionary
```

The spec is pinned rather than fetched at runtime so this builds offline and in CI, and so a
spec change is a reviewed diff rather than a silent shift in the output.

## Where the output goes

`.gitignore` rejects `*.xlsx` — deliverables live in the Cowork folder, not here. The default
output lands in `data/` (also ignored). Copy it to
`../claude_work/supporting_files/excel_output/` when publishing.

## Caveats worth keeping in mind

- **Grain is measured, not declared.** Each grain is the smallest column combination unique in
  the largest sampled response file. Where files disagree the workbook says so rather than
  picking a winner. Some endpoints come back undetermined; that is a real answer.
- **Profiling samples.** The largest few payload files per endpoint, capped at 6,000 records.
  Null rates and distinct counts describe that sample, not the whole corpus.
- **`manifest.json` is not data.** It sits in every raw directory and, read as data, yields a
  convincing but meaningless grain of `filename`.
- **Nested dot-paths have no observed columns.** The profiler measures top-level keys only.
