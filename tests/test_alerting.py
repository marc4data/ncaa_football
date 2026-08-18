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
    # the test suite never reaches the network.
    assert result == {"logged": True, "triaged": False, "emailed": False}
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
