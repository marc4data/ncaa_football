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
import json
import os
import smtplib
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

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


def send_failure_email(event: Dict[str, Any]) -> bool:
    """Send the failure by SMTP if configured. Returns whether it was sent."""
    if not smtp_configured():
        return False
    try:
        message = EmailMessage()
        message["Subject"] = f"[cfdb] {event.get('dag_id')}.{event.get('task_id')} failed"
        message["From"] = os.environ[SMTP_FROM]
        message["To"] = os.environ[SMTP_TO]
        message.set_content(
            "\n".join(f"{k}: {v}" for k, v in event.items() if k != "traceback")
            + "\n\n"
            + str(event.get("traceback") or "")
        )

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
        return False


def build_event(context: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten an Airflow task context into a record worth reading later."""
    task_instance = context.get("task_instance")
    exception = context.get("exception")
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "dag_id": getattr(task_instance, "dag_id", None) or context.get("dag_id"),
        "task_id": getattr(task_instance, "task_id", None) or context.get("task_id"),
        "run_id": getattr(task_instance, "run_id", None),
        "try_number": getattr(task_instance, "try_number", None),
        "log_url": getattr(task_instance, "log_url", None),
        "error": str(exception) if exception else None,
        "traceback": (
            "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            if isinstance(exception, BaseException) else None
        ),
    }


def failure_callback(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Airflow `on_failure_callback`: log locally, and email when configured."""
    event = build_event(context or {})
    logged = record_failure(event)
    emailed = send_failure_email(event)
    print(f"ALERT: {event.get('dag_id')}.{event.get('task_id')} failed "
          f"(logged={logged}, emailed={emailed}): {event.get('error')}")
    return {"logged": logged, "emailed": emailed}
