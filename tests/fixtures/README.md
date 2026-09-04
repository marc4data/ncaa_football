# Spec artefacts, vendored

Copies of files Marc authored in `claude_work/supporting_files/`, checked in here so the
tests that assert against them run in CI.

`claude_work` is a SIBLING of this repository, not part of it. A test reading `../claude_work`
passes on a laptop and finds nothing on a CI runner — where `Path.glob` on a missing directory
yields nothing and raises nothing, so the test would go green while checking zero fields. That
is the same defect `ci/check_page_queries.py` carried for months.

| File | Authored by | Asserted by |
|---|---|---|
| `cfdb_scores_column_order.csv` | Marc, 2026-09-04 | `test_the_scores_sheet_carries_every_field_marc_listed` |

If Marc revises one of these, re-copy it and let the test say what changed.
