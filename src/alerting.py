"""Failure alerting for pipeline tasks.

Data quality rule #5: pipeline failures must be visible, never swallowed. Two channels,
chosen because neither needs new infrastructure:

  1. A local JSONL file — always written. The site can surface it, and it works with no
     configuration at all, which matters because an alerting channel that needs setup is
     an alerting channel that is off on the day it's needed.
  2. SMTP email — sent only when configured. Credentials come from the environment.

Nothing in here may raise. An exception in a failure handler would mask the failure it
exists to report, so every path is wrapped and degrades to a printed warning.
"""
import argparse
import json
import os
import smtplib
import socket
import sys
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

from .alert_triage import triage, unavailable_reason

ALERT_LOG = Path("data") / "alerts" / "failures.jsonl"

SMTP_HOST = "ALERT_SMTP_HOST"
SMTP_PORT = "ALERT_SMTP_PORT"
SMTP_USER = "ALERT_SMTP_USER"
SMTP_PASSWORD = "ALERT_SMTP_PASSWORD"
SMTP_FROM = "ALERT_EMAIL_FROM"
SMTP_TO = "ALERT_EMAIL_TO"


def smtp_configured() -> bool:
    """True when enough SMTP settings exist to attempt a send."""
    return all(os.getenv(k) for k in (SMTP_HOST, SMTP_FROM, SMTP_TO))


def record_failure(event: Dict[str, Any], path: Optional[Path] = None) -> bool:
    """Append one failure record to the local log. Returns whether it was written.

    The destination is resolved at call time, not bound as a default argument — a default
    would freeze the module-level value at import and make the path impossible to redirect.
    """
    path = path or ALERT_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
        return True
    except Exception as exc:  # never raise from an alert path
        print(f"ALERT: could not write failure log: {exc}")
        return False


def diagnose(exc: BaseException) -> str:
    """Turn an SMTP exception into the thing to actually go and fix."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return ("Credentials rejected. Gmail requires an App Password (16 characters, "
                "2-Step Verification enabled) — an account password will always fail here.")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return f"Sender refused. {SMTP_FROM} usually has to match {SMTP_USER}."
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return f"Recipient refused. Check {SMTP_TO}."
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return ("Server rejected STARTTLS. Port 465 expects TLS from the first byte; "
                "this client upgrades an open connection, so use 587.")
    if isinstance(exc, (socket.gaierror, socket.herror)):
        return f"Host did not resolve. Check {SMTP_HOST} (Gmail is smtp.gmail.com)."
    if isinstance(exc, (ConnectionRefusedError, socket.timeout, TimeoutError)):
        return f"Nothing answered. Check {SMTP_PORT} (587 for STARTTLS) and any firewall."
    return "Unexpected SMTP error — see the exception above."


def format_email(event: Dict[str, Any],
                 summary: Optional[Dict[str, str]] = None,
                 triage_note: Optional[str] = None) -> Tuple[str, str]:
    """Build the subject and body. Pure, so the exact email can be tested and previewed.

    Subject is `[cfdb] FAILURE - <headline>`: a constant prefix so a filter or a sort can
    find every one of them, followed by what actually broke, so the subject alone is often
    enough. Without triage the headline degrades to `dag.task` — less useful, still
    correctly shaped.

    The body puts the readable explanation first and the technical detail underneath. Both
    are always present: the summary is what makes the alert actionable at a glance, and the
    traceback is what makes it debuggable when the summary is wrong.
    """
    identity = f"{event.get('dag_id')}.{event.get('task_id')}"

    if summary:
        subject = f"[cfdb] FAILURE - {summary.get('headline')}"
        sections = [
            f"{identity}  |  attempt {event.get('try_number')}  |  {event.get('at')}",
            "",
            "WHAT HAPPENED",
            summary.get("what_happened", "(not provided)"),
            "",
            "IMPACT",
            summary.get("impact", "(not provided)"),
            "",
            "LIKELY FIX",
            summary.get("likely_fix", "(not provided)"),
            "",
            f"-- written by {summary.get('model', 'Claude')}; the detail below is the source"
            " of truth --",
        ]
    else:
        subject = f"[cfdb] FAILURE - {identity} failed"
        sections = [
            f"{identity}  |  attempt {event.get('try_number')}  |  {event.get('at')}",
            "",
            str(event.get("error") or "(no error message recorded)"),
        ]
        # SAY THAT THE SUMMARY IS MISSING, AND WHY.
        #
        # The plain email is a correct, working fallback, which is exactly what made this
        # dangerous: an invalid API key produced 21 consecutive alerts with no summary and
        # nothing anywhere in the email saying one had been attempted. The degradation hid
        # inside a fallback that looked like a design choice, and was found only by asking
        # why the readable section had stopped appearing.
        #
        # A missing capability that announces itself is a nuisance. One that does not is an
        # assumption that quietly stops being true.
        if triage_note:
            # The API's own message usually ends in a full stop; ours adds one. Trimmed so
            # the line does not read "API key is invalid.." to the person we are asking to
            # go and fix the API key.
            sections += [
                "",
                f"(No readable summary: {triage_note.rstrip('. ')}. This alert is "
                "unaffected — the detail below is complete.)",
            ]

    sections += [
        "",
        "=" * 72,
        "TECHNICAL DETAIL",
        "=" * 72,
        "",
        "\n".join(f"{k}: {v}" for k, v in event.items() if k != "traceback"),
        "",
        str(event.get("traceback") or "(no traceback captured)"),
    ]
    return subject, "\n".join(sections)


def send_failure_email(event: Dict[str, Any], raise_on_error: bool = False,
                       summary: Optional[Dict[str, str]] = None,
                       triage_note: Optional[str] = None) -> bool:
    """Send the failure by SMTP if configured. Returns whether it was sent.

    `raise_on_error` is for the CLI test, where a silent False is useless — a person
    running a test wants the actual reason.
    """
    if not smtp_configured():
        return False
    try:
        subject, body = format_email(event, summary, triage_note)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = os.environ[SMTP_FROM]
        message["To"] = os.environ[SMTP_TO]
        message.set_content(body)

        port = int(os.getenv(SMTP_PORT, "587"))
        with smtplib.SMTP(os.environ[SMTP_HOST], port, timeout=30) as server:
            server.starttls()
            user, password = os.getenv(SMTP_USER), os.getenv(SMTP_PASSWORD)
            if user and password:
                server.login(user, password)
            server.send_message(message)
        return True
    except Exception as exc:  # never raise from an alert path
        print(f"ALERT: could not send failure email: {exc}")
        if raise_on_error:
            raise
        return False


# Lines the databricks driver, dbt and psycopg2 all emit on the way down. Ordered by how
# specific they are, because the useful line is rarely the last one — a stack unwinds into
# generic wrappers, and "Retry policy max retry duration" says more than "task failed".
ERROR_MARKERS = (
    "Retry request would exceed",
    "Database Error",
    "Compilation Error",
    "OperationalError",
    "Exception:",
    "Traceback (most recent call last)",
    "Error:",
)
LOG_ROOT = Path(os.getenv("AIRFLOW__LOGGING__BASE_LOG_FOLDER", "/opt/airflow/logs"))


def error_from_log(dag_id: Optional[str], run_id: Optional[str], task_id: Optional[str],
                   try_number: Optional[int]) -> Optional[str]:
    """The most informative error line from the task's own log file.

    THE LAST RESORT THAT SHOULD RARELY BE NEEDED AND WAS. Airflow 3 runs tasks under a
    supervisor and the exception does not always survive that boundary, so
    `context["exception"]` can be None for a task that raised with a perfectly good message.
    A Databricks sync failed twice with "Retry request would exceed Retry policy max retry
    duration of 900.0 seconds" sitting in its log, and the alert email said
    "(no error message recorded)".

    An alert that links to a log it cannot read has outsourced its only job. This reads it.

    Never raises, never blocks: a missing log, a permission error or a half-written file all
    return None, and the alert goes out with whatever else it has.
    """
    if not all((dag_id, run_id, task_id)):
        return None
    try:
        folder = LOG_ROOT / f"dag_id={dag_id}" / f"run_id={run_id}" / f"task_id={task_id}"
        if not folder.is_dir():
            return None
        # Prefer this attempt's log, then any attempt — a retry-exhausted task writes one
        # file per try and the last is the one that gave up.
        candidates = sorted(folder.glob("attempt=*.log"))
        if try_number is not None:
            exact = folder / f"attempt={try_number}.log"
            if exact.exists():
                candidates = [exact] + [c for c in candidates if c != exact]
        for path in candidates:
            text = path.read_text(errors="ignore")[-200_000:]
            hits = []
            for line in text.splitlines():
                for rank, marker in enumerate(ERROR_MARKERS):
                    if marker in line:
                        # Structured logs wrap the message in JSON; pull the event out so
                        # the email carries a sentence rather than a serialised record.
                        message = line
                        if '"event":"' in line:
                            try:
                                message = json.loads(line[line.index("{"):])["event"]
                            except Exception:                      # noqa: BLE001
                                pass
                        hits.append((rank, message.strip()[:600]))
                        break
            if hits:
                hits.sort(key=lambda pair: pair[0])
                return hits[0][1]
    except Exception as exc:                                       # noqa: BLE001
        print(f"could not read the task log for an error message: {exc}")
    return None


def build_event(context: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten an Airflow task context into a record worth reading later.

    THREE SOURCES FOR THE ERROR, in descending order of directness, because depending on
    one of them is how an alert ends up saying nothing. `exception` is the best answer and
    is absent under Airflow 3's supervisor more often than it should be; `reason` is what
    Airflow itself says happened; the log is where the message provably was.

    `error_source` travels with it so a reader knows which one answered — "from the task
    log" and "from the raised exception" are different levels of confidence and the email
    should not pretend otherwise.
    """
    task_instance = context.get("task_instance")
    exception = context.get("exception")
    dag_id = getattr(task_instance, "dag_id", None) or context.get("dag_id")
    task_id = getattr(task_instance, "task_id", None) or context.get("task_id")
    run_id = getattr(task_instance, "run_id", None)
    try_number = getattr(task_instance, "try_number", None)

    error = str(exception) if exception else None
    source = "raised exception" if error else None
    if not error:
        reason = context.get("reason")
        if reason:
            error, source = str(reason), "Airflow reason"
    if not error:
        from_log = error_from_log(dag_id, run_id, task_id, try_number)
        if from_log:
            error, source = from_log, "task log"

    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "dag_id": dag_id,
        "task_id": task_id,
        "run_id": run_id,
        "try_number": try_number,
        "log_url": getattr(task_instance, "log_url", None),
        "error": error,
        "error_source": source,
        "traceback": (
            "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            if isinstance(exception, BaseException) else None
        ),
    }


def already_alerted(event: Dict[str, Any], window_seconds: int = 600) -> bool:
    """Whether this exact failure has already been emailed.

    Identity is (dag_id, task_id, run_id, try_number) — the four things that make one
    attempt distinct. A retry is a new try_number and alerts again, which is correct: the
    second failure of the same task is news.

    Read from the append-only record rather than from memory, because the callback may run
    in a fresh process each time. A window bounds the scan so this stays cheap as the log
    grows; anything older than ten minutes is a different incident by any useful definition.
    """
    keys = ("dag_id", "task_id", "run_id", "try_number")
    identity = tuple(event.get(k) for k in keys)
    if not any(identity):
        return False
    try:
        if not ALERT_LOG.exists():
            return False
        cutoff = datetime.now(timezone.utc).timestamp() - window_seconds
        for line in ALERT_LOG.read_text(errors="ignore").splitlines()[-400:]:
            try:
                past = json.loads(line)
            except Exception:                                      # noqa: BLE001
                continue
            if past.get("at") == event.get("at"):
                continue                                # the record we just wrote
            if tuple(past.get(k) for k in keys) != identity:
                continue
            try:
                when = datetime.fromisoformat(str(past.get("at"))).timestamp()
            except Exception:                                      # noqa: BLE001
                continue
            if when >= cutoff:
                return True
    except Exception as exc:                                       # noqa: BLE001
        # Never let dedup logic cost an alert. A failure to read the log means send it.
        print(f"could not check for duplicate alerts ({exc}); sending anyway")
    return False


def failure_callback(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Airflow `on_failure_callback`: log locally, and email when configured.

    Order matters. The local record is written *first* and without the summary, so the
    durable evidence of the failure exists before anything slow or networked is attempted.
    Triage then runs, and its result is appended as its own line rather than rewritten into
    the first — an append-only log stays append-only, and a summary that never arrived
    leaves the original record untouched rather than half-written.
    """
    event = build_event(context or {})
    logged = record_failure(event)

    if already_alerted(event):
        # ONE EMAIL PER FAILURE. Airflow 3 invoked this callback twice, two seconds apart,
        # for the same (dag, task, run, attempt) — so a single Databricks failure sent two
        # identical alerts. Duplicate alerts are worse than merely noisy: they train the
        # reader to skim, and the one that matters arrives looking like the one that did
        # not.
        #
        # Deduped on the failure's own identity rather than on time, so a genuine retry
        # (a new attempt) still alerts. The local record above is written FIRST and
        # unconditionally — the durable evidence keeps both, and only the email is
        # suppressed.
        print(f"suppressing a duplicate alert for {event.get('dag_id')}."
              f"{event.get('task_id')} attempt {event.get('try_number')}")
        return {"logged": logged, "emailed": False, "duplicate": True}

    # Defence in depth. `triage` already promises never to raise, but that promise lives in
    # another module and one careless edit there would silently cost us the email — the
    # exact failure this module exists to prevent. The guarantee is cheap to enforce here
    # too, so it is enforced here too.
    try:
        summary = triage(event)
        triage_note = None if summary else unavailable_reason()
    except Exception as exc:  # never raise from an alert path
        print(f"ALERT: triage raised, sending the plain email ({type(exc).__name__}: {exc})")
        summary = None
        triage_note = f"{type(exc).__name__}: {exc}"

    if summary:
        record_failure({"at": event.get("at"), "dag_id": event.get("dag_id"),
                        "task_id": event.get("task_id"), "run_id": event.get("run_id"),
                        "kind": "triage", **summary})

    emailed = send_failure_email(event, summary=summary, triage_note=triage_note)
    print(f"ALERT: {event.get('dag_id')}.{event.get('task_id')} failed "
          f"(logged={logged}, triaged={bool(summary)}, emailed={emailed}): "
          f"{event.get('error')}")
    return {"logged": logged, "triaged": bool(summary), "emailed": emailed}


def _describe_config() -> None:
    """Print which channels are live, without ever printing a secret."""
    print(f"local log:  {ALERT_LOG}  (always on)")
    print("smtp:")
    for key in (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_FROM, SMTP_TO):
        value = os.getenv(key)
        print(f"  {key:22} {value or '(unset)'}")
    password = os.getenv(SMTP_PASSWORD)
    print(f"  {SMTP_PASSWORD:22} {'set, ' + str(len(password)) + ' chars' if password else '(unset)'}")
    if password and len(password.replace(' ', '')) != 16:
        print("    note: Gmail App Passwords are 16 characters — this may be an account password.")
    print(f"\nsmtp configured: {smtp_configured()}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and test failure alerting without running any pipeline.")
    parser.add_argument("--check", action="store_true",
                        help="report configuration; send nothing")
    parser.add_argument("--test", action="store_true",
                        help="send a synthetic failure through both channels")
    args = parser.parse_args()

    load_dotenv()

    if not args.check and not args.test:
        parser.print_help()
        return 0

    _describe_config()
    if args.check:
        return 0

    event = build_event({
        "task_instance": None,
        "exception": RuntimeError("synthetic alert from `python -m src.alerting --test`"),
    })
    event.update({"dag_id": "cfdb_alerting", "task_id": "self_test"})

    print("\n--- sending ---")
    logged = record_failure(event)
    print(f"local log: {'written' if logged else 'FAILED'} -> {ALERT_LOG}")

    if not smtp_configured():
        print("smtp:      skipped (not configured)")
        return 0 if logged else 1

    try:
        send_failure_email(event, raise_on_error=True)
    except Exception as exc:
        print(f"smtp:      FAILED — {type(exc).__name__}")
        print(f"           {diagnose(exc)}")
        return 1
    print(f"smtp:      sent to {os.getenv(SMTP_TO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
