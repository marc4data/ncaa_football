"""Tests for failure alerting.

The load-bearing property is that nothing here raises: an exception in a failure handler
would mask the failure it exists to report.
"""
import json

import pytest

from src import alerting


class FakeTaskInstance:
    dag_id = "cfbd_lines_snapshot"
    task_id = "snapshot_lines"
    run_id = "manual__2026-08-15"
    try_number = 2
    log_url = "http://localhost:8080/log"


def test_record_failure_appends_one_json_line(tmp_path):
    path = tmp_path / "alerts" / "failures.jsonl"

    assert alerting.record_failure({"error": "first"}, path) is True
    assert alerting.record_failure({"error": "second"}, path) is True

    lines = path.read_text().strip().split("\n")
    assert [json.loads(x)["error"] for x in lines] == ["first", "second"]


def test_record_failure_never_raises_on_bad_path(tmp_path):
    """A broken alert sink must not take down the failure handler."""
    unwritable = tmp_path / "a-file"
    unwritable.write_text("not a directory")

    assert alerting.record_failure({"error": "x"}, unwritable / "nested" / "f.jsonl") is False


def test_build_event_flattens_the_airflow_context():
    error = ValueError("CFBD returned 500")
    event = alerting.build_event({"task_instance": FakeTaskInstance(), "exception": error})

    assert event["dag_id"] == "cfbd_lines_snapshot"
    assert event["task_id"] == "snapshot_lines"
    assert event["try_number"] == 2
    assert event["error"] == "CFBD returned 500"
    assert event["at"].endswith("+00:00")


def test_smtp_is_skipped_when_unconfigured(monkeypatch):
    for key in (alerting.SMTP_HOST, alerting.SMTP_FROM, alerting.SMTP_TO):
        monkeypatch.delenv(key, raising=False)

    assert alerting.smtp_configured() is False
    assert alerting.send_failure_email({"dag_id": "d", "task_id": "t"}) is False


def test_smtp_send_uses_starttls_and_configured_recipients(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"], sent["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            sent["starttls"] = True

        def login(self, user, password):
            sent["login"] = user

        def send_message(self, message):
            sent["to"] = message["To"]
            sent["subject"] = message["Subject"]

    monkeypatch.setattr(alerting.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv(alerting.SMTP_HOST, "smtp.example.com")
    monkeypatch.setenv(alerting.SMTP_PORT, "587")
    monkeypatch.setenv(alerting.SMTP_FROM, "pipeline@example.com")
    monkeypatch.setenv(alerting.SMTP_TO, "marc@example.com")
    monkeypatch.setenv(alerting.SMTP_USER, "pipeline@example.com")
    monkeypatch.setenv(alerting.SMTP_PASSWORD, "secret")

    assert alerting.send_failure_email({"dag_id": "d", "task_id": "t"}) is True
    assert sent["starttls"] is True
    assert sent["to"] == "marc@example.com"
    assert "d.t failed" in sent["subject"]


def test_smtp_failure_is_swallowed(monkeypatch):
    def explode(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(alerting.smtplib, "SMTP", explode)
    monkeypatch.setenv(alerting.SMTP_HOST, "smtp.example.com")
    monkeypatch.setenv(alerting.SMTP_FROM, "pipeline@example.com")
    monkeypatch.setenv(alerting.SMTP_TO, "marc@example.com")

    assert alerting.send_failure_email({"dag_id": "d", "task_id": "t"}) is False


def test_failure_callback_reports_both_channels(tmp_path, monkeypatch):
    monkeypatch.setattr(alerting, "ALERT_LOG", tmp_path / "failures.jsonl")
    for key in (alerting.SMTP_HOST, alerting.SMTP_FROM, alerting.SMTP_TO):
        monkeypatch.delenv(key, raising=False)

    result = alerting.failure_callback({"task_instance": FakeTaskInstance(),
                                        "exception": RuntimeError("boom")})

    # `triaged` is False with no ANTHROPIC_API_KEY set, which is also the assertion that
    # the test suite never reaches the network. `webhook` joined the report when the droplet
    # turned out to have no working SMTP path at all — the callback now tries both and says
    # which, if either, left the host.
    assert result == {"logged": True, "triaged": False, "emailed": False, "webhook": False}
    assert "boom" in (tmp_path / "failures.jsonl").read_text()


def test_diagnose_maps_auth_failure_to_the_app_password_hint():
    """The most likely misconfiguration deserves the most specific advice."""
    exc = alerting.smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    assert "App Password" in alerting.diagnose(exc)


def test_diagnose_covers_the_other_common_smtp_failures():
    import socket

    assert "smtp.gmail.com" in alerting.diagnose(socket.gaierror("name resolution"))
    assert "587" in alerting.diagnose(ConnectionRefusedError())
    assert "465" in alerting.diagnose(alerting.smtplib.SMTPNotSupportedError())
    assert "Unexpected" in alerting.diagnose(ValueError("something else"))


def test_send_can_raise_for_the_cli_test(monkeypatch):
    """A silent False is useless to someone running a test on purpose."""
    def explode(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(alerting.smtplib, "SMTP", explode)
    for key, value in ((alerting.SMTP_HOST, "smtp.example.com"),
                       (alerting.SMTP_FROM, "a@example.com"),
                       (alerting.SMTP_TO, "b@example.com")):
        monkeypatch.setenv(key, value)

    assert alerting.send_failure_email({"dag_id": "d", "task_id": "t"}) is False
    with pytest.raises(OSError):
        alerting.send_failure_email({"dag_id": "d", "task_id": "t"}, raise_on_error=True)


# --- the alert that said nothing ---------------------------------------------------------

def test_the_error_survives_a_missing_exception(tmp_path, monkeypatch):
    """Airflow 3 runs tasks under a supervisor and the exception does not always cross that
    boundary, so context["exception"] can be None for a task that raised with a perfectly
    good message. A Databricks sync failed twice with "Retry request would exceed Retry
    policy max retry duration of 900.0 seconds" in its log while the email said
    "(no error message recorded)".
    """
    from src import alerting
    folder = (tmp_path / "dag_id=d" / "run_id=r" / "task_id=t")
    folder.mkdir(parents=True)
    (folder / "attempt=2.log").write_text(
        '{"level":"info","event":"starting"}\n'
        '{"level":"error","event":"ThriftBackend: Retry request would exceed Retry policy '
        'max retry duration of 900.0 seconds"}\n')
    monkeypatch.setattr(alerting, "LOG_ROOT", tmp_path)
    found = alerting.error_from_log("d", "r", "t", 2)
    assert found is not None
    assert "Retry request would exceed" in found
    # The JSON wrapper is unwrapped — an email should carry a sentence, not a record.
    assert not found.startswith("{")


def test_the_most_specific_error_line_wins(tmp_path, monkeypatch):
    """A stack unwinds into generic wrappers, so the LAST error line is rarely the useful
    one. "Retry policy max retry duration" says more than "Error: task failed"."""
    from src import alerting
    folder = (tmp_path / "dag_id=d" / "run_id=r" / "task_id=t")
    folder.mkdir(parents=True)
    (folder / "attempt=1.log").write_text(
        "Retry request would exceed Retry policy max retry duration\n"
        "Error: task failed\n")
    monkeypatch.setattr(alerting, "LOG_ROOT", tmp_path)
    assert "Retry request" in alerting.error_from_log("d", "r", "t", 1)


def test_reading_the_log_never_raises(tmp_path, monkeypatch):
    """A missing log, a permission error or a half-written file must cost nothing. Nothing
    in an alert path may raise — that is the whole contract of this module."""
    from src import alerting
    monkeypatch.setattr(alerting, "LOG_ROOT", tmp_path / "does-not-exist")
    assert alerting.error_from_log("d", "r", "t", 1) is None
    assert alerting.error_from_log(None, None, None, None) is None


def test_one_email_per_attempt_but_a_retry_still_alerts(tmp_path, monkeypatch):
    """Airflow invoked the callback twice, two seconds apart, for the same attempt — one
    failure, two identical emails. Duplicates train the reader to skim, and then the one
    that matters arrives looking like the one that did not.

    Deduped on the failure's identity, not on time, so a genuine retry is still news.
    """
    from datetime import datetime, timezone
    from src import alerting
    log = tmp_path / "failures.jsonl"
    log.write_text("")
    monkeypatch.setattr(alerting, "ALERT_LOG", log)

    def event(try_number):
        return {"at": datetime.now(timezone.utc).isoformat(), "dag_id": "d",
                "task_id": "t", "run_id": "r", "try_number": try_number}

    first = event(2)
    assert alerting.already_alerted(first) is False
    alerting.record_failure(first)
    assert alerting.already_alerted(event(2)) is True     # Airflow's second call
    assert alerting.already_alerted(event(3)) is False    # a real retry


# === the droplet cannot send email, and pretending otherwise cost eight hours ==============

def test_a_blocked_network_is_diagnosed_as_blocked_rather_than_misconfigured():
    """ERRNO 101 IS NOT A SETTINGS PROBLEM.

    Measured on the droplet 2026-09-04: SMTP ports 25, 465, 587 and 2525 are all unreachable
    while 443 to GitHub and to CFBD is open. DigitalOcean blocks outbound SMTP by default.

    Every failure that day logged "could not send failure email" and stopped there, which
    reads like a transient and invites another look at the credentials. It cannot be fixed by
    a credential or a port, and the message has to say so or the next person spends the
    afternoon on App Passwords.
    """
    from errno import ENETUNREACH
    note = alerting.diagnose(OSError(ENETUNREACH, "Network is unreachable"))
    assert "blocks outbound SMTP" in note
    assert "EMAIL CANNOT BE THE ALERT PATH" in note
    assert alerting.WEBHOOK_URL in note, "it must name the path that does work"


def test_the_webhook_is_the_path_that_works_and_never_raises(monkeypatch):
    """443 is open and every SMTP port is not, so an HTTPS POST is the only alert this host
    can send itself.

    NEVER RAISES, for the reason `heartbeat.ping` does not: an alerting outage must not fail
    the callback that is already reporting a failure.
    """
    monkeypatch.setenv(alerting.WEBHOOK_URL, "https://example.invalid/hook")

    def explode(*_a, **_k):
        raise OSError("no route to host")

    monkeypatch.setattr(alerting.urllib.request, "urlopen", explode)
    assert alerting.send_webhook("subject", "body") is False


def test_the_webhook_payload_suits_the_receivers_it_is_likely_to_meet(monkeypatch):
    """`text` for Slack, `content` for Discord, both carrying the same string — so the
    receiver can be swapped for whatever Marc picks without a code change."""
    import json
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(request, timeout=None):
        captured["body"] = json.loads(request.data.decode())
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setenv(alerting.WEBHOOK_URL, "https://hooks.example/abc")
    monkeypatch.setattr(alerting.urllib.request, "urlopen", fake)
    assert alerting.send_webhook("[cfdb] FAILURE - dbt_test", "it broke") is True
    assert captured["body"]["text"] == captured["body"]["content"]
    assert "dbt_test" in captured["body"]["text"]
    assert captured["body"]["source"] == "cfdb"


def test_no_webhook_configured_is_not_an_error(monkeypatch):
    """A box with no webhook is the state today. It must be quiet about it here and loud in
    the callback, not the other way round."""
    monkeypatch.delenv(alerting.WEBHOOK_URL, raising=False)
    assert alerting.send_webhook("s", "b") is False


def test_the_callback_says_so_when_nothing_left_the_host(tmp_path, monkeypatch, capsys):
    """THE ASSUMPTION THAT COST EIGHT HOURS. "Alerting is configured" was true and useless:
    the email path could not work and nothing said the alert had gone nowhere."""
    monkeypatch.setattr(alerting, "ALERT_LOG", tmp_path / "failures.jsonl")
    for key in (alerting.SMTP_HOST, alerting.SMTP_FROM, alerting.SMTP_TO,
                alerting.WEBHOOK_URL):
        monkeypatch.delenv(key, raising=False)

    alerting.failure_callback({"task_instance": FakeTaskInstance(),
                               "exception": RuntimeError("boom")})
    printed = capsys.readouterr().out
    assert "NOTHING LEFT THIS HOST" in printed
    assert "GitHub heartbeat watcher" in printed, (
        "it must name what detection now depends on, or the log is just an apology")


def test_the_callback_actually_attempts_the_webhook(tmp_path, monkeypatch):
    """CALLING IT IS THE HALF THAT MATTERS. Hardcoding the result to False broke no test,
    because every assertion was about the printed summary rather than about the attempt —
    and a webhook nobody calls is the same as no webhook, which is the state that cost eight
    hours."""
    monkeypatch.setattr(alerting, "ALERT_LOG", tmp_path / "failures.jsonl")
    for key in (alerting.SMTP_HOST, alerting.SMTP_FROM, alerting.SMTP_TO):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(alerting.WEBHOOK_URL, "https://hooks.example/abc")

    sent = {}
    monkeypatch.setattr(alerting, "send_webhook",
                        lambda subject, body: sent.update(subject=subject, body=body) or True)

    result = alerting.failure_callback({"task_instance": FakeTaskInstance(),
                                        "exception": RuntimeError("boom")})
    assert result["webhook"] is True
    assert "FAILURE" in sent["subject"], "the webhook gets the same subject the email would"
    assert "boom" in sent["body"]
