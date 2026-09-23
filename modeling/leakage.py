"""The leakage guard: no feature list reaches a model if it carries the answer.

LEAKAGE is a model being shown, while it learns, something it could not know before kickoff.
It does not break anything. It makes the model look brilliant in testing and useless on a
real Saturday, and nothing in the numbers says which one you are looking at.

Two kinds are refused here:

  - OUTCOMES: the final score, and anything computed from it. `margin` is the answer; a
    model given it learns to copy it.
  - THE MARKET: the closing `spread`. It is the benchmark we are graded against, and a model
    fed the line learns to repeat the line — there is no edge left to measure (spec §5).

The guard matches exact names AND name tokens, because a derived column rarely keeps its
parent's name: `home_win`, `total_points`, `ats_cover` are all outcomes. It deliberately does
NOT match the bare token `points`, because `home_points_per_opportunity_offense` is a real
pre-game feature. Pass `also_forbid=` for any derived column the patterns cannot see.

This is a name check, so it is a floor, not a proof. It catches the mistake that actually
happens — an outcome column left in a list — not a feature someone built from the score and
then named innocently. That second kind is caught by review, and by a feature being too good.
"""
import re
from typing import Iterable, Sequence

# `total` is matched by exact name only: as a token it would catch `home_total_havoc_offense`.
OUTCOME_COLUMNS = frozenset({"home_points", "away_points", "margin", "spread", "total", "total_points", "over_under"})

# A token is a whole `_`-separated word, so `ats` does not match `stats`.
DERIVED_TOKENS = ("margin", "spread", "cover", "ats", "win", "winner", "result", "score")
_TOKEN_RE = re.compile(r"(?:^|_)(" + "|".join(DERIVED_TOKENS) + r")(?:_|$)")


class LeakageError(ValueError):
    """A feature list contains an outcome, or a column derived from one."""


def leaking_columns(features: Iterable[str], also_forbid: Sequence[str] = ()) -> list:
    """The members of `features` that must not be model inputs, in the order given."""
    forbidden = OUTCOME_COLUMNS | set(also_forbid)
    return [f for f in features if f in forbidden or _TOKEN_RE.search(f)]


def assert_no_leakage(features: Iterable[str], also_forbid: Sequence[str] = ()) -> list:
    """Return the feature list unchanged, or raise LeakageError naming every offender."""
    features = list(features)
    bad = leaking_columns(features, also_forbid)
    if bad:
        raise LeakageError(
            f"refused: {len(bad)} feature(s) carry the outcome or the market line: {bad}. "
            "Outcomes are targets, and the closing spread is the benchmark — neither is an input."
        )
    return features


# What the pack's CSV holds that is not a pre-game feature. Kept separate from
# OUTCOME_COLUMNS on purpose: this list decides what the builder offers, the guard checks it
# independently, and a mistake in one is caught by the other.
NOT_FEATURES = (
    "id", "start_date", "season", "season_type",
    "home_team", "away_team", "home_conference", "away_conference",
    "home_points", "away_points", "margin", "spread",
)


def pack_feature_columns(columns: Iterable[str]) -> list:
    """The pack's pre-game feature columns, already passed through the guard."""
    return assert_no_leakage([c for c in columns if c not in NOT_FEATURES])
