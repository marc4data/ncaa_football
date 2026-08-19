"""Build the CFBD data dictionary workbook.

    python -m src.data_dictionary

The spec is not fetched here on purpose. `src/ingest.py` owns every call to CFBD; this tool
reads a pinned copy at `config/api-docs.json` so it runs in CI, offline, and against a known
version. Refresh it by downloading https://apinext.collegefootballdata.com/api-docs.json over
that file — the diff is then a reviewable record of what CFBD changed.

The workbook does NOT belong in this repo: `.gitignore` rejects `*.xlsx` because deliverables
live in the Cowork folder. The default output goes to `data/` (also ignored); copy the result
to ../claude_work/supporting_files/excel_output/ when publishing it.

Almost everything on the Gaps sheet is COMPUTED rather than written down, so the sheet stays
true when this is re-run. The one thing that is not computable — why an endpoint is absent —
comes from the strategy and note already recorded in `src/endpoints.py`, not from a second
opinion maintained here.
"""
import argparse
import json
from datetime import date
from pathlib import Path

from src.endpoints import REGISTRY, LIVE, MANUAL, PER_GAME

from . import definitions as dfn
from .profile import landed_keys, profile_all
from .spec import Spec
from .workbook import build

# Raw tables dbt declares as sources. Kept here rather than parsed out of _sources.yml because
# a missing source should show up as a dictionary diff to review, not vanish silently.
DBT_SOURCES = {
    "teams", "games", "venues", "conferences", "calendar", "lines", "games_teams", "records",
}

# Two vocabularies sharing at least this fraction of their values are near-misses worth
# flagging; below it they are simply different lists.
VOCABULARY_OVERLAP = 0.6

STRATEGY_REASON = {
    MANUAL: "Registry strategy MANUAL — needs an argument no sweep can invent",
    PER_GAME: "Registry strategy PER_GAME — one call per game; opt-in only",
    LIVE: "Registry strategy LIVE — only meaningful during a game in progress",
}


def compute_gaps(spec, endpoints, fields, profile, registry_by_key, landed):
    gaps = []

    # --- endpoints the spec offers that we have not landed ------------------------------
    for path in sorted(spec.doc.get("paths", {})):
        key = path.strip("/").replace("/", "_")
        if key in landed:
            continue
        registered = registry_by_key.get(key)
        if registered is None:
            gaps.append(["Endpoint not landed", path,
                         "In the spec but absent from src/endpoints.py — the registry is out of "
                         "date with the spec.", "Add to registry"])
            continue
        reason = STRATEGY_REASON.get(registered.strategy,
                                     "Registry strategy {}".format(registered.strategy))
        if registered.note:
            reason += " ({})".format(registered.note)
        action = "Expected — excluded by design" if not registered.include else "Land it"
        gaps.append(["Endpoint not landed", path, reason + ".", action])

    # --- calls that failed ---------------------------------------------------------------
    for key, profiled in sorted(profile.items()):
        failed = profiled.get("failed_calls") or {}
        if not failed:
            continue
        total = sum(failed.values())
        calls = profiled.get("manifest_calls", 0)
        registered = registry_by_key.get(key)
        detail = "{} of {} recorded calls failed (status {}).".format(
            total, calls, ", ".join(str(s) for s in sorted(failed)))
        if registered is not None and not registered.include:
            detail += (" This endpoint is include=False in the registry, so the sweep does not "
                       "call it — these are residue from a manual or historical invocation, not "
                       "a live pipeline fault. The error files remain on disk.")
            action = "Clean up raw dir"
        else:
            detail += " This endpoint IS in the default sweep."
            action = "Fix extractor"
        gaps.append(["Failed API calls", key, detail, action])

    # --- error responses persisted alongside good ones -----------------------------------
    if any(p.get("failed_calls") for p in profile.values()):
        gaps.append([
            "Stored errors", "non-200 responses are written to data/raw",
            "Failed responses are written into the raw tree alongside good ones and recorded in "
            "the manifest with their status code. Anything measuring freshness by file presence "
            "alone would count an error as a successful refresh.",
            "Check mart_data_freshness filters on status_code"])

    # --- vocabularies that nearly agree, and so will be assumed to agree -----------------
    # Detected by VALUE overlap, not by name. DivisionClassification and
    # ConferenceClassification share no name prefix but differ by exactly one value, which is
    # the sort of near-miss that gets discovered by a broken join rather than by reading.
    vocabularies = {v["name"]: set(v["values"]) for v in spec.vocabularies()}
    for name, values in sorted(vocabularies.items()):
        for other, other_values in sorted(vocabularies.items()):
            if other <= name:
                continue
            only_a, only_b = values - other_values, other_values - values
            if not (only_a or only_b):
                continue  # identical sets are not a conflict
            union = values | other_values
            if not union or len(values & other_values) / len(union) < VOCABULARY_OVERLAP:
                continue
            gaps.append([
                "Vocabulary conflict", "{} vs {}".format(name, other),
                "{:.0%} of values shared, but not interchangeable. Only in {}: {}. Only in {}: "
                "{}. Check which one types each column before joining on either.".format(
                    len(values & other_values) / len(union),
                    name, ", ".join(sorted(only_a)) or "(none)",
                    other, ", ".join(sorted(only_b)) or "(none)"),
                "Design around it"])

    # --- raw directories with no endpoint behind them ------------------------------------
    stray = sorted(k for k in landed if k not in {p.strip("/").replace("/", "_")
                                                  for p in spec.doc.get("paths", {})})
    if stray:
        gaps.append(["Stray raw directory", ", ".join(stray),
                     "Holds payload files but matches no path in the spec — left over from a "
                     "probe or a renamed endpoint. Nothing downstream should read it.",
                     "Remove or explain"])

    # --- payload shape anomalies ---------------------------------------------------------
    mixed = sorted(k for k, p in profile.items() if len(p.get("shapes") or []) > 1)
    if mixed:
        gaps.append(["Shape anomaly", "mixed payload shapes",
                     "More than one payload shape on disk for: {}. Any loader must handle all "
                     "of them.".format(", ".join(mixed)), "Verify loader"])

    scalar_only = sorted({f["key"] for f in fields if f["field_path"] == "(scalar)"})
    if scalar_only:
        gaps.append(["Shape anomaly", ", ".join(scalar_only),
                     "Returns a bare array of scalars rather than objects, so it has no named "
                     "fields and cannot be modelled like the others.",
                     "Model as a lookup list"])

    # --- empty payloads -------------------------------------------------------------------
    empty = sum(p.get("empty_files", 0) for p in profile.values())
    total_files = sum(p.get("files", 0) for p in profile.values())
    if empty:
        gaps.append(["Empty payloads", "{} of {} payload files".format(empty, total_files),
                     "Status 200 with an empty data array. Expected where a season has been "
                     "requested before it has been played — not a defect, but they skew any "
                     "per-file record-count metric.", "No action"])

    # --- undetermined grain ----------------------------------------------------------------
    undetermined = sorted(k for k in landed if not (profile.get(k, {}).get("unique")))
    if undetermined:
        gaps.append(["Grain undetermined", "{} endpoints".format(len(undetermined)),
                     "No combination of up to three columns was unique in the sampled file for: "
                     "{}. Their grain is unresolved.".format(", ".join(undetermined)),
                     "Resolve before modelling"])

    # --- how much of this document is CFBD's word ------------------------------------------
    described = sum(1 for f in fields if f["description"])
    gaps.append(["Definition gap",
                 "{} of {} spec fields carry no description".format(
                     len(fields) - described, len(fields)),
                 "CFBD publishes descriptions for almost no response fields. Endpoint and "
                 "parameter descriptions are complete; field meaning is published nowhere except "
                 "the Glossary's {} concepts.".format(len(dfn.GLOSSARY)),
                 "This workbook is the substitute"])
    return gaps


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", default="config/api-docs.json",
                        help="Path to the CFBD OpenAPI JSON")
    parser.add_argument("--raw", default="data/raw", help="Raw landing directory")
    parser.add_argument("--out", default="data/cfbd_data_dictionary.xlsx",
                        help="Workbook output path")
    parser.add_argument("--profile-out", default="", help="Optional path for the observed profile JSON")
    args = parser.parse_args(argv)

    with open(args.spec) as fh:
        spec = Spec(json.load(fh))

    raw_dir = Path(args.raw)
    landed = set(landed_keys(raw_dir))
    registry_by_key = {e.key: e for e in REGISTRY}

    endpoints, fields, parameters = spec.extract(keys=landed)
    profile = profile_all(raw_dir, keys=sorted(landed))
    gaps = compute_gaps(spec, endpoints, fields, profile, registry_by_key, landed)

    if args.profile_out:
        with open(args.profile_out, "w") as fh:
            json.dump(profile, fh, indent=2)

    counts = build(spec, endpoints, fields, parameters, profile, registry_by_key,
                   DBT_SOURCES, gaps, args.out, date.today().isoformat())
    print("spec v{} · landed {} endpoints".format(spec.version, len(landed)))
    print("wrote {} ({})".format(args.out, ", ".join(
        "{} {}".format(v, k) for k, v in counts.items())))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
