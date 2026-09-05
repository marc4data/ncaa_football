"""The deploy instructions must describe the deploy that exists.

Two failures on 2 September, one after the other, both from this file:

  1. It rsynced `deploy/site/Dockerfile`, a SECOND copy CI never built, which still said
     `COPY pages/` months after the rename to `views/`. The build failed outright. Its
     neighbouring requirements.txt said `streamlit>=1.40` instead of the `==1.61.1` pin that
     exists because an unpinned upgrade blanked every page on 30 August — the build failing
     first is the only reason that did not ship too. `deploy/site/` is now deleted.

  2. With the paths corrected, the manual path SUCCEEDED and still broke the site. Production
     is two halves — the site image and the pipeline repo Airflow builds and publishes from —
     and the manual path only ever knew about one. The site went to main, the pipeline stayed
     four PRs behind, and Schedule rendered "Something went wrong reading srv_game" because
     the page selected three columns the older pipeline had not built.

`scripts/deploy_main.sh` does both halves and verifies them, and existed the whole time.
These tests fail if the README stops pointing at it, or starts documenting a hand-run
alternative to it again.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / "deploy" / "README.md"
SCRIPT = REPO / "scripts" / "deploy_main.sh"
CI = REPO / ".github" / "workflows" / "ci.yml"


def _redeploy_section() -> str:
    text = README.read_text()
    start = text.index("Redeploy after merging to main")
    return text[start:text.index("Verify after deploying", start)]


def test_the_readme_names_the_deploy_script():
    assert SCRIPT.exists(), "the script the README points at must exist"
    assert "scripts/deploy_main.sh" in _redeploy_section()


def _code_blocks(section: str) -> str:
    """Only the fenced commands.

    THE SIXTH TIME IN THIS REPO A SOURCE-READING TEST HAS MATCHED ITS OWN PROSE. The first
    version of the assertion below searched the whole section for "rsync " and found it in
    the sentence explaining why rsync is not documented there. A rule about what someone can
    COPY AND RUN has to be asserted against the runnable text and nothing else.
    """
    return "\n".join(re.findall(r"```(?:bash)?\n(.*?)```", section, re.S))


def test_the_readme_does_not_offer_a_hand_run_alternative():
    """A manual rsync deploys the site and silently leaves the pipeline behind. Reproducing
    the commands here is what made that the default thing to do."""
    commands = _code_blocks(_redeploy_section())
    assert commands.strip(), "the redeploy section has no runnable block at all"
    for forbidden in ("rsync ", "docker compose build site", "$CFDB_DROPLET_HOST:"):
        assert forbidden not in commands, (
            f"{forbidden!r} is runnable in the redeploy section again; the script is the "
            f"deploy")


def test_the_script_deploys_both_halves_of_production():
    """The premise of the advice above. If the script stops touching the pipeline repo, the
    README is telling people it does something it no longer does."""
    body = SCRIPT.read_text()
    assert "/opt/cfdb-pipeline" in body, "the pipeline half"
    assert "/opt/cfdb/site" in body, "the site half"
    assert "site_smoke.py" in body, "and it verifies the site renders"


def test_there_is_exactly_one_site_dockerfile():
    """A second copy of a file CI does not check will drift. It drifted once already, into a
    build failure and an unpinned Streamlit."""
    found = sorted(p.relative_to(REPO).as_posix()
                   for p in REPO.rglob("Dockerfile")
                   if "site" in p.parts and ".venv" not in p.parts)
    assert found == ["site/Dockerfile"], found


def test_the_dockerfile_ci_builds_is_the_one_the_script_ships():
    """`docker build ... site/` uses `site/Dockerfile`; the script tars `site/`. Same tree,
    so the green check is about the thing that reaches the droplet."""
    assert "docker build -t cfdb-site:ci site/" in CI.read_text()
    assert re.search(r"tar czf - -C site \.", SCRIPT.read_text())


def test_no_document_tells_anyone_to_copy_site_pages():
    """`pages/` is the name Streamlit auto-discovers as a multipage app, which is why the
    directory was renamed to `views/`. Instructions kept saying `pages` long after."""
    for doc in (REPO / "deploy").rglob("*.md"):
        assert not re.search(r"\bsite/pages\b", doc.read_text()), doc


def test_the_deploy_rebuilds_and_publishes_the_data_it_changes():
    """R-126. Moving the pipeline repo updates the SQL; it does not run it.

    The scores DAG that would normally rebuild is gated on the live-scoring window, so outside
    one it correctly succeeds having done nothing — and a serving-model change merged midweek
    reaches the site on Saturday. On 2 September that left Schedule reading three columns the
    published table did not have.

    THE DECISION MOVED OUT OF THE SHELL (R-273). It used to be a directory diff and a
    `publish_all` inlined here; both now live in `src/deploy_models.py`, where they can be
    tested. What this asserts is that the script still HAS the step and still has the manual
    override — the rest is covered by tests/test_deploy_models.py.
    """
    body = SCRIPT.read_text()
    assert "src.deploy_models" in body, "the rebuild-and-publish step is gone entirely"
    assert "--rebuild" in body, "the full-rebuild override must survive"
    assert "fail \"model rebuild/publish failed\"" in body, (
        "a failed rebuild must fail the deploy rather than be reported and passed over")


def test_the_rebuild_selects_on_state_so_it_cannot_miss_an_upstream_change():
    """THE BLIND SPOT IS CLOSED, AND THIS IS THE TEST THAT USED TO DOCUMENT IT.

    Its previous form asserted that the script WROTE DOWN what its directory diff could not
    see — an upstream change to fct_game, dim_team or a staging view that alters serving
    output without touching `dbt/models/serving/`. Accepting a known gap and recording it was
    the right trade while the alternative was expensive; it stopped being the right trade when
    the artefact that removes the gap turned out to already exist on the droplet.

    So the assertion inverts: not "the gap is documented" but "there is no gap". A state
    comparison sees a changed macro and a changed upstream model, and `+` carries the rebuild
    down to every serving table that reads them.
    """
    from pathlib import Path as _P
    module = (_P(__file__).resolve().parents[1] / "src" / "deploy_models.py").read_text()
    assert "state:modified+" in module
    assert "tag:production" in module
    # The old trigger must be gone rather than left beside the new one — two triggers is two
    # answers to "does this need rebuilding", and the weaker one wins by running first.
    # CODE ONLY. The comments still name the old trigger, and should — the reason the diff
    # was replaced is worth more to the next reader than the diff was.
    code = "\n".join(ln for ln in SCRIPT.read_text().splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "dbt/models/serving/" not in code, (
        "the directory diff is still running in the deploy script")
