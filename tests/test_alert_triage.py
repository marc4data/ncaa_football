"""Tests for the failure-triage summariser.

The property that matters most is negative: this code runs *inside* the failure path, so
no input, no outage and no malformed reply may stop the alert going out. Most of what
follows is proving the fallbacks, not the happy path.
"""
import json
import urllib.error

import pytest

from src import alert_triage
from src.alerting import format_email

EVENT = {
    "at": "2026-08-18T08:00:03Z",
    "dag_id": "cfbd_lines_snapshot",
    "task_id": "cadence_gate",
    "run_id": "scheduled__2026-08-18T08:00:00+00:00",
    "try_number": 1,
    "error": "[Errno 2] No such file or directory: 'config/lines_cadence.json'",
    "traceback": "Traceback (most recent call last):\n  ...\nFileNotFoundError",
}

SUMMARY = {
    "headline": "Cadence config missing from the Airflow mount",
    "what_happened": "The gate could not read its config file.",
    "impact": "No snapshot this run. Nothing was lost; the next run recovers.",
    "likely_fix": "Recreate the containers to re-establish the bind mount.",
    "model": "claude-sonnet-5",
}


# --- redaction -------------------------------------------------------------------------

def test_secret_values_are_stripped_before_leaving_the_machine(monkeypatch):
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi0123456789abcdef")
    text = "auth failed for token dapi0123456789abcdef on host"
    assert "dapi0123456789abcdef" not in alert_triage.redact(text)
    assert "<DATABRICKS_TOKEN redacted>" in alert_triage.redact(text)


def test_short_secrets_are_left_alone(monkeypatch):
    """A two-character secret would match half the traceback and destroy it."""
    monkeypatch.setenv("PG_PASSWORD", "cf")
    assert alert_triage.redact("the config file was not found") == \
        "the config file was not found"


def test_url_credentials_are_stripped_even_when_we_do_not_know_them():
    text = "postgresql+psycopg2://cfdb:supersecret@postgres:5432/airflow"
    redacted = alert_triage.redact(text)
    assert "supersecret" not in redacted
    assert "cfdb:<redacted>@postgres" in redacted


def test_bearer_tokens_are_stripped():
    redacted = alert_triage.redact("Authorization: Bearer abcdef0123456789xyz")
    assert "abcdef0123456789xyz" not in redacted


def test_redact_handles_none():
    assert alert_triage.redact(None) is None


# --- prompt ----------------------------------------------------------------------------

def test_prompt_carries_the_facts_needed_to_diagnose():
    prompt = alert_triage.build_prompt(EVENT)
    assert "cfbd_lines_snapshot" in prompt
    assert "cadence_gate" in prompt
    assert "lines_cadence.json" in prompt


def test_a_huge_traceback_is_trimmed_from_the_front():
    """The raising frame is at the end, so that is the end to keep."""
    event = dict(EVENT, traceback="x" * 50_000 + "\nTheActualError")
    prompt = alert_triage.build_prompt(event)
    assert len(prompt) < alert_triage.MAX_TRACEBACK_CHARS + 2000
    assert "TheActualError" in prompt


def test_a_missing_traceback_does_not_break_the_prompt():
    prompt = alert_triage.build_prompt({"dag_id": "d", "task_id": "t"})
    assert "(no traceback captured)" in prompt


# --- failure modes: none of these may raise ---------------------------------------------

def test_no_api_key_returns_none_quietly(monkeypatch):
    """The normal state on a fresh machine, not an error."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert alert_triage.triage(EVENT) is None


def test_an_http_error_returns_none(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def boom(*_args, **_kwargs):
        raise urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(alert_triage, "_post", boom)
    assert alert_triage.triage(EVENT) is None


def test_a_timeout_returns_none(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def boom(*_args, **_kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(alert_triage, "_post", boom)
    assert alert_triage.triage(EVENT) is None


def test_a_non_json_reply_returns_none(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(alert_triage, "_post", lambda *a, **k: {
        "content": [{"type": "text", "text": "I'm afraid I can't do that."}]})
    assert alert_triage.triage(EVENT) is None


def test_a_reply_without_a_headline_returns_none(monkeypatch):
    """The subject line is the point; a summary without one is not usable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(alert_triage, "_post", lambda *a, **k: {
        "content": [{"type": "text", "text": json.dumps({"impact": "bad"})}]})
    assert alert_triage.triage(EVENT) is None


# --- parsing ---------------------------------------------------------------------------

def test_a_fenced_reply_is_parsed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fenced = "```json\n" + json.dumps(SUMMARY) + "\n```"
    monkeypatch.setattr(alert_triage, "_post", lambda *a, **k: {
        "model": "claude-sonnet-5", "content": [{"type": "text", "text": fenced}]})
    result = alert_triage.triage(EVENT)
    assert result["headline"] == SUMMARY["headline"]


def test_json_embedded_in_prose_is_recovered(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    text = "Here you go:\n" + json.dumps(SUMMARY) + "\nHope that helps."
    monkeypatch.setattr(alert_triage, "_post", lambda *a, **k: {
        "model": "m", "content": [{"type": "text", "text": text}]})
    assert alert_triage.triage(EVENT)["impact"] == SUMMARY["impact"]


# --- the email itself --------------------------------------------------------------------

def test_subject_starts_with_the_standard_prefix_then_the_headline():
    subject, _ = format_email(EVENT, SUMMARY)
    assert subject.startswith("[cfdb] FAILURE - ")
    assert SUMMARY["headline"] in subject


def test_body_leads_with_the_explanation_and_keeps_the_detail_below():
    _, body = format_email(EVENT, SUMMARY)
    assert body.index("WHAT HAPPENED") < body.index("IMPACT") < body.index("LIKELY FIX")
    assert body.index("LIKELY FIX") < body.index("TECHNICAL DETAIL")
    # The raw material is still there — the summary is a lead, not a replacement.
    assert EVENT["traceback"] in body
    assert EVENT["run_id"] in body


def test_without_triage_the_email_still_has_the_standard_shape():
    """Degraded, not broken: the prefix and the traceback both survive."""
    subject, body = format_email(EVENT, None)
    assert subject.startswith("[cfdb] FAILURE - ")
    assert "cfbd_lines_snapshot.cadence_gate" in subject
    assert EVENT["traceback"] in body
    assert EVENT["error"] in body


@pytest.mark.parametrize("summary", [None, {}, SUMMARY])
def test_format_email_never_raises(summary):
    subject, body = format_email(EVENT, summary)
    assert subject and body


def test_failure_callback_still_alerts_when_triage_explodes(monkeypatch, tmp_path):
    """The property this whole module is subordinate to.

    A summariser that raises must not stop the alert. If this ever fails, the feature is a
    liability rather than an improvement.
    """
    from src import alerting

    def exploding_triage(_event):
        raise RuntimeError("triage is broken")

    monkeypatch.setattr(alerting, "triage", exploding_triage)
    monkeypatch.setattr(alerting, "ALERT_LOG", tmp_path / "failures.jsonl")
    monkeypatch.delenv("ALERT_SMTP_HOST", raising=False)

    result = alerting.failure_callback({"dag_id": "d", "task_id": "t"})

    # The callback completes and reports honestly that triage did not happen.
    assert result["logged"] is True
    assert result["triaged"] is False
    # The durable record was written before triage was ever attempted, which is why the
    # ordering in failure_callback is load-bearing rather than incidental.
    assert (tmp_path / "failures.jsonl").exists()


def test_email_is_still_sent_when_triage_explodes(monkeypatch, tmp_path):
    """The summariser failing must cost us the summary, never the alert."""
    from src import alerting

    sent = {}

    def capture(event, raise_on_error=False, summary=None):
        sent["subject"], sent["body"] = alerting.format_email(event, summary)
        return True

    monkeypatch.setattr(alerting, "triage",
                        lambda _e: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(alerting, "send_failure_email", capture)
    monkeypatch.setattr(alerting, "ALERT_LOG", tmp_path / "failures.jsonl")

    result = alerting.failure_callback({"dag_id": "cfbd_x", "task_id": "t"})

    assert result["emailed"] is True
    assert sent["subject"].startswith("[cfdb] FAILURE - ")
