"""The deploy instructions must ship the files CI actually checks.

On 2 September a documented deploy failed with `"/pages": not found`. The cause was not a
typo in the README: there were TWO Dockerfiles. CI built `site/Dockerfile`, which was
correct; the README shipped `deploy/site/Dockerfile`, which still said `COPY pages/` months
after the directory was renamed to `views/`, and whose requirements.txt said
`streamlit>=1.40` instead of the `==1.61.1` pin that exists because an unpinned upgrade
blanked every page on 30 August.

So the green "site image builds and renders" check was true and irrelevant — it validated a
file that never left the laptop. These pin the property that makes it relevant.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / "deploy" / "README.md"
CI = REPO / ".github" / "workflows" / "ci.yml"


def _redeploy_block() -> str:
    """The bash block under "Redeploy after changing site code"."""
    text = README.read_text()
    start = text.index("Redeploy after changing site code")
    return text[start:text.index("```", text.index("```bash", start) + 7)]


def test_there_is_exactly_one_site_dockerfile():
    """A second copy of a file CI does not check is a defect waiting to recur. It recurred
    once already, and the only reason the stale requirements did not also ship is that the
    stale Dockerfile failed the build first."""
    found = sorted(p.relative_to(REPO).as_posix()
                   for p in REPO.rglob("Dockerfile")
                   if "site" in p.parts and ".venv" not in p.parts)
    assert found == ["site/Dockerfile"], found


def test_the_readme_ships_the_dockerfile_ci_builds():
    """`docker build ... site/` uses `site/Dockerfile`. If the README rsyncs a different one,
    the check is green about a file that never reaches the droplet."""
    assert "docker build -t cfdb-site:ci site/" in CI.read_text(), (
        "CI's build target moved; this test's premise needs rechecking")
    block = _redeploy_block()
    assert "site/Dockerfile" in block
    assert "site/requirements.txt" in block
    assert "deploy/site/" not in block


def test_the_readme_ships_views_and_not_pages():
    """`pages/` is the name Streamlit auto-discovers as a multipage app, which is why the
    directory was renamed. The README kept saying `pages` long after the rename, so the
    rsync failed with `link_stat ... No such file or directory` before docker even ran."""
    block = _redeploy_block()
    assert "site/views" in block
    assert not re.search(r"\bsite/pages\b", block)


def test_every_path_the_readme_rsyncs_exists():
    """The failure mode this whole file exists for: an instruction naming a path that was
    renamed or deleted. Checked against the filesystem rather than by eye."""
    block = _redeploy_block()
    paths = re.findall(r"(?<![\w/])((?:site|deploy)/[\w./-]+)", block)
    assert paths, "no paths found; the block's shape changed"
    missing = [p for p in paths if not (REPO / p).exists()]
    assert not missing, f"the deploy instructions name paths that do not exist: {missing}"


def test_the_readme_tells_the_reader_to_load_the_env_file():
    """Every command in the block interpolates $CFDB_DROPLET_HOST, and an interactive shell
    does not read .env. Without this the rsync targets a bare `:/opt/cfdb/`."""
    assert ". ./.env" in _redeploy_block()
