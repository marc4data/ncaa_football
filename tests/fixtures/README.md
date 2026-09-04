# Spec artefacts, vendored

Copies of files Marc authored in `claude_work/supporting_files/`, checked in here so the
tests that assert against them run in CI.

`claude_work` is a SIBLING of this repository, not part of it. A test reading `../claude_work`
passes on a laptop and finds nothing on a CI runner — where `Path.glob` on a missing directory
yields nothing and raises nothing, so the test would go green while checking zero fields. That
is the same defect `ci/check_page_queries.py` carried for months.

| File | Authored by | Asserted by |
|---|---|---|
| `cfdb_scores_column_order_v2.csv` | Marc, 2026-09-05 | `test_the_sheet_is_exactly_the_order_and_the_categories_marc_asked_for` |

v2 supersedes the 131-field v1 list, which predated the Market block and carried no category
column. It is 144 rows of Position/Field/Category, so the test can assert the block structure
and not only its contents.

If Marc revises one of these, re-copy it and let the test say what changed.
