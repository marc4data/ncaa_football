"""Record how far the Airflow deploy tree has drifted from main.

The worktree pin fixed "a dev checkout silently changes production scheduling" and created
its mirror image: production silently keeps running old code. Both are the same divergence;
the pin only changed which direction it runs in.

That is how production spent a day building a dbt project with 39 models while development
had 56 — no error, no alert, and the only reason it surfaced was counting models by hand.
A divergence that is visible is an inconvenience; this one was invisible.

The pin still requires a person to run scripts/deploy_main.sh. This does not automate that
— deliberately, because automatic advancement would give back the protection the pin
exists for. It makes the gap measurable, and lets System Overview raise it.
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "cfdb_deploy"

# Commits behind main. Chosen rather than elapsed time because one commit that changes a DAG
# matters more than a week of none, and staleness is about content, not clock.
WARN_AT = 1
ERROR_AT = 5


def _git(args, cwd) -> Optional[str]:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=30).stdout.strip() or None
    except Exception:                                            # noqa: BLE001
        return None


def deploy_status(deploy_dir: Optional[Path] = None) -> Dict:
    """How far behind origin/main the deploy tree is."""
    directory = deploy_dir or DEPLOY_DIR
    if not directory.exists():
        return {"observed_at": datetime.now(timezone.utc).isoformat(),
                "severity": "unknown", "detail": f"No deploy tree at {directory}"}

    _git(["fetch", "origin", "main", "--quiet"], directory)
    deploy_sha = _git(["rev-parse", "--short", "HEAD"], directory)
    main_sha = _git(["rev-parse", "--short", "origin/main"], directory)
    behind_raw = _git(["rev-list", "--count", "HEAD..origin/main"], directory)
    behind = int(behind_raw) if behind_raw and behind_raw.isdigit() else None

    if behind is None:
        severity, detail = "unknown", "Could not determine distance from origin/main"
    elif behind == 0:
        severity, detail = "ok", f"Deploy tree matches main at {deploy_sha}"
    elif behind >= ERROR_AT:
        severity = "error"
        detail = (f"Deploy tree is {behind} commits behind main "
                  f"({deploy_sha} vs {main_sha}). Airflow is running old code — "
                  f"run scripts/deploy_main.sh")
    else:
        severity = "warn"
        detail = (f"Deploy tree is {behind} commit(s) behind main "
                  f"({deploy_sha} vs {main_sha}). Run scripts/deploy_main.sh")

    return {"observed_at": datetime.now(timezone.utc).isoformat(),
            "deploy_sha": deploy_sha, "main_sha": main_sha,
            "commits_behind": behind, "severity": severity, "detail": detail}


DDL = """
CREATE TABLE IF NOT EXISTS raw.raw_deploy_status (
    observed_at timestamptz NOT NULL,
    deploy_sha text,
    main_sha text,
    commits_behind int,
    severity text,
    detail text,
    PRIMARY KEY (observed_at)
)
"""


def record(status: Optional[Dict] = None) -> int:
    """Land one observation so srv_system_health can surface it."""
    from .load_raw_to_postgres import get_conn

    status = status or deploy_status()
    connection = get_conn()
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cursor.execute(DDL)
            cursor.execute("""
                INSERT INTO raw.raw_deploy_status
                    (observed_at, deploy_sha, main_sha, commits_behind, severity, detail)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (observed_at) DO NOTHING
            """, (status["observed_at"], status.get("deploy_sha"), status.get("main_sha"),
                  status.get("commits_behind"), status["severity"], status["detail"]))
        return 1
    finally:
        connection.close()


def main() -> int:
    status = deploy_status()
    print(f"  {status['severity'].upper()}: {status['detail']}")
    record(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
