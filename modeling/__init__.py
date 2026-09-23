"""cfdb's predictive-modeling workspace (session `wtc`).

Three small modules, and the order they are used in is the order they are listed:

    data      load the licensed training pack from its gitignored path, and check its contract
    splits    train <= 2023 · validate 2024 · test 2025, regular season only
    evaluate  score predictions beside the market's own numbers on the same rows

plus `leakage`, the guard every feature list passes through before a model sees it.

LICENCE BOUNDARY. The pack (`cfdb_model_pack/`) is personal, non-commercial and may not be
uploaded to a public repository. Nothing in this package is copied from it: the code is
written fresh, it reads the pack from disk at run time, and the pack path is gitignored and
refused by `scripts/pre-commit`.

SIGN CONVENTION, the pack's, never flipped: `margin = away_points - home_points`, so a
negative margin means the home team won, and a negative `spread` means home was favoured.
"""
