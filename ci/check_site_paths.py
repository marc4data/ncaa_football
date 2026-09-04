"""Assert no module under `site/` resolves a path outside `site/`.

THE THIRD COLLISION WITH ONE BOUNDARY, AND THE FIRST GUARD FOR IT.

`deploy/docker-compose.yml` builds the site image with `context: ./site`. Everything above
that directory is outside the build context, so a `COPY` cannot reach it and a path resolved
at runtime finds nothing. The container has `/app` and no repo.

That has now bitten three times, each time silently:

  R-099   `.streamlit/config.toml` lived at the repo root, so the deployed radio stayed
          Streamlit red while the local one was correct. Streamlit looked for
          /app/.streamlit/config.toml, found nothing, and used its own default.
  ---     `lib/lines_cadence.json` exists at all because this image cannot import `src/`.
  R-224   `lib/metrics.py` read `dbt/dbt_project.yml` for the upset thresholds and fell back
          to hardcoded values. The fallback matched, so the page was CORRECT BY COINCIDENCE
          and would have gone stale the day a var changed.

The guard for the first two was "remember", which is why there was a third. Meanwhile
`ci/check_layering.py` enforces the dbt layer boundary from the manifest, automatically — so
the repo guarded its DATA boundary by machine and its DEPLOYMENT boundary by memory. This is
the missing half.

WHAT IT CHECKS. Any `Path(__file__)...parents[n]` whose result lies above `site/`, and any
literal path string that names a top-level directory the image does not contain. Static, so
it runs in CI without a container and cannot be defeated by the path simply not existing on
the machine running the tests — which is exactly how the last one passed review.

WHAT IT DOES NOT CHECK. Paths assembled at runtime from variables. A determined caller can
still escape; the point is that the three ways it has actually happened are now impossible to
merge, not that escape is unthinkable.
"""
import ast
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

# Directories that exist in the repo and NOT in the image. Naming one from inside site/ is
# always a mistake, however the path is built.
OUTSIDE_THE_IMAGE = ("dbt/", "src/", "dags/", "config/", "deploy/", "tests/", "ci/",
                     "docs/", "scripts/", "cfdb_model_pack/", "model_outputs/")


def _depth_from_site(path: Path) -> int:
    """How many directories deep under `site/` this module sits. site/app.py is 1."""
    return len(path.relative_to(SITE).parts)


def _parents_escapes(path: Path, index: int) -> bool:
    """Does `Path(__file__).resolve().parents[index]` land above site/?

    `site/lib/x.py` has parents[0] = site/lib and parents[1] = site — both fine. parents[2] is
    the repo root, which does not exist in the image.
    """
    return index >= _depth_from_site(path)


def violations() -> list:
    found = []
    for module in sorted(SITE.rglob("*.py")):
        if "__pycache__" in module.parts:
            continue
        try:
            tree = ast.parse(module.read_text(encoding="utf-8"))
        except SyntaxError as error:                       # noqa: PERF203
            found.append((module, 0, f"does not parse: {error}"))
            continue

        for node in ast.walk(tree):
            # Path(__file__)...parents[N]
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "parents"
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, int)):
                index = node.slice.value
                if _parents_escapes(module, index):
                    found.append((
                        module, node.lineno,
                        f"parents[{index}] resolves above site/, which is outside the "
                        f"image's build context"))

            # A literal naming a directory the image does not have, or climbing out of the
            # tree with `..`. The second was missed by the first version of this check and
            # found by testing it against R-099's actual shape — a config referenced as
            # `../.streamlit/config.toml`, which escapes without naming anything.
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                # A URL is not a filesystem path, and one containing `/src/` is a false
                # positive — the kind that gets a check switched off rather than obeyed.
                if text.startswith(("http://", "https://", "mailto:", "//")):
                    continue
                if text.startswith("../") or "/../" in text:
                    found.append((
                        module, node.lineno,
                        f"{text!r} climbs out of site/ with '..', which resolves to nothing "
                        f"in the container"))
                    continue
                for outside in OUTSIDE_THE_IMAGE:
                    if text.startswith(outside) or f"/{outside}" in text:
                        found.append((
                            module, node.lineno,
                            f"names {outside!r}, which is not in the site image"))
                        break
    return found


def main() -> int:
    if not SITE.exists():
        print(f"::error::{SITE} does not exist — this check scanned nothing")
        return 1

    modules = [p for p in SITE.rglob("*.py") if "__pycache__" not in p.parts]
    # A SCAN THAT FINDS NOTHING IS THE FAILURE THIS REPO ALREADY SHIPPED ONCE:
    # ci/check_page_queries.py globbed a renamed directory and passed while checking nothing.
    if len(modules) < 15:
        print(f"::error::only {len(modules)} modules under site/ — the scan is not finding "
              f"the tree it is supposed to check")
        return 1

    found = violations()
    for module, line, reason in found:
        print(f"::error file={module.relative_to(SITE.parent)},line={line}::{reason}")
    if found:
        print(f"\n{len(found)} path(s) reach outside site/. The image is built with "
              f"`context: ./site`, so they resolve to nothing in the container — and a "
              f"fallback that happens to be correct today is the failure mode, not an error.")
        return 1
    print(f"Checked {len(modules)} modules under site/. None resolves a path outside it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
