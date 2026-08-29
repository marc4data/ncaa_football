"""Tests for the failure-triage summariser.

The property that matters most is negative: this code runs *inside* the failure path, so
no input, no outage and no malformed reply may stop the alert going out. Most of what
follows is proving the fallbacks, not the happy path.
"""
import io
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

    def capture(event, raise_on_error=False, summary=None, triage_note=None):
        sent["subject"], sent["body"] = alerting.format_email(event, summary, triage_note)
        return True

    monkeypatch.setattr(alerting, "triage",
                        lambda _e: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(alerting, "send_failure_email", capture)
    monkeypatch.setattr(alerting, "ALERT_LOG", tmp_path / "failures.jsonl")

    result = alerting.failure_callback({"dag_id": "cfbd_x", "task_id": "t"})

    assert result["emailed"] is True
    assert sent["subject"].startswith("[cfdb] FAILURE - ")


def test_the_suite_cannot_reach_the_network_by_accident(assert_no_network, tmp_path):
    """Regression guard for a defect this suite actually had.

    When ANTHROPIC_API_KEY landed in .env, `failure_callback` began making a real, billable
    call on every test run — and still passed, so nothing surfaced it but an 11.5-second
    test that used to take milliseconds. The autouse fixture in conftest strips ambient
    credentials; this proves the result, not the mechanism.
    """
    from src import alerting

    alerting.ALERT_LOG = tmp_path / "failures.jsonl"
    result = alerting.failure_callback({"dag_id": "d", "task_id": "t"})

    assert result["triaged"] is False
    assert result["emailed"] is False


# --- a broken summariser must announce itself ---------------------------------------------

def test_an_unavailable_summary_says_why_in_the_email(monkeypatch):
    """A working fallback is the worst place for a degradation to hide.

    The key in .env was rejected with "API key is invalid" on 21 consecutive alerts. Every
    one still sent, the plain email is perfectly reasonable, and the only trace was a line
    of stdout inside a failing task's log. Nothing in the email said a summary had been
    attempted at all, so the feature looked switched off rather than broken.
    """
    from src import alerting
    event = {"dag_id": "d", "task_id": "t", "error": "boom"}
    _, body = alerting.format_email(
        event, None, "HTTP 401 from the Anthropic API — API key is invalid.")
    assert "No readable summary" in body
    assert "API key is invalid" in body
    # The alert itself must still be complete — the note explains an absence, never replaces
    # content.
    assert "TECHNICAL DETAIL" in body and "boom" in body


def test_a_successful_summary_carries_no_apology(monkeypatch):
    """The note appears only when there is something missing to explain."""
    from src import alerting
    summary = {"headline": "h", "what_happened": "w", "impact": "i", "likely_fix": "f"}
    _, body = alerting.format_email({"dag_id": "d", "task_id": "t"}, summary, None)
    assert "No readable summary" not in body


def test_the_reason_is_recorded_for_every_way_triage_can_give_up(monkeypatch):
    """`unavailable_reason` is what the email reads, so it must be set on every None path —
    a reason of None would put the alert straight back to saying nothing."""
    from src import alert_triage
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert alert_triage.triage(EVENT) is None
    assert "ANTHROPIC_API_KEY" in (alert_triage.unavailable_reason() or "")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(alert_triage, "_post",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down")))
    assert alert_triage.triage(EVENT) is None
    assert "network down" in (alert_triage.unavailable_reason() or "")

    monkeypatch.setattr(alert_triage, "_post",
                        lambda *a, **k: {"content": [{"type": "text", "text": "not json"}]})
    assert alert_triage.triage(EVENT) is None
    assert "could not be parsed" in (alert_triage.unavailable_reason() or "")


# --- preflight: the check that would have caught the dead key on day one ------------------

def test_check_credentials_distinguishes_unrecognised_from_unscoped(monkeypatch):
    """401 and 403 need different fixes, and the probe exists to tell them apart.

    /v1/models requires no workspace scoping, so `authentication_error` there means the key
    is not recognised at all — a workspace ID cannot help. A 403 would mean a real key
    pointed somewhere it is not allowed, which IS a workspace question.
    """
    import urllib.error
    from src import alert_triage as t
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def raise_status(code, body):
        def boom(*_a, **_k):
            raise urllib.error.HTTPError("u", code, "reason", {}, io.BytesIO(body.encode()))
        return boom

    monkeypatch.setattr(t.urllib.request, "urlopen",
                        raise_status(401, '{"error":{"message":"API key is invalid."}}'))
    ok, detail = t.check_credentials()
    assert not ok and "not recognised" in detail and "workspace ID will not help" in detail
    assert "invalid.." not in detail          # the API's full stop plus ours

    monkeypatch.setattr(t.urllib.request, "urlopen",
                        raise_status(403, '{"error":{"message":"not permitted"}}'))
    ok, detail = t.check_credentials()
    assert not ok and "workspace" in detail and "not recognised" not in detail


def test_check_credentials_reports_a_missing_key_without_a_network_call(monkeypatch):
    from src import alert_triage as t
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(t.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("must not call the API with no key"))
    ok, detail = t.check_credentials()
    assert not ok and "ANTHROPIC_API_KEY is not set" in detail


# --- the token budget, which thinking now shares ------------------------------------------

def test_truncation_names_the_token_limit_not_the_parser(monkeypatch):
    """"could not be parsed" sent us to look at the parser when the answer was in `usage`.

    Sonnet 5 runs adaptive thinking by default and thinking tokens come out of max_tokens.
    Measured on a real alert: 828 output tokens of which 400 were thinking, leaving 72 spare
    against the old 900 budget. On 29 August it did not fit, the JSON was cut off mid-object
    and the email lost its summary. A reason that blames the wrong component is worse than a
    vague one.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(alert_triage, "_post", lambda *a, **k: {
        "stop_reason": "max_tokens",
        "usage": {"output_tokens": 2000, "output_tokens_details": {"thinking_tokens": 1600}},
        "content": [{"type": "text", "text": '{"headline":"truncated mid-obj'}]})
    assert alert_triage.triage(EVENT) is None
    reason = alert_triage.unavailable_reason() or ""
    assert "cut off" in reason and "thinking" in reason and "MAX_TOKENS" in reason


def test_the_budget_leaves_real_headroom_over_observed_use():
    """Observed on a live alert: ~830 output tokens, ~400 of them thinking. A budget that
    merely fits is a coin flip on every alert."""
    assert alert_triage.MAX_TOKENS >= 1800


def test_the_reply_shape_is_enforced_server_side(monkeypatch):
    """output_config.format makes the schema the API's problem rather than the parser's.
    `_parse` stays as the backstop for truncation, which structured output cannot prevent."""
    sent = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(alert_triage, "_post",
                        lambda payload, key: sent.update(payload) or {
                            "model": "m", "stop_reason": "end_turn",
                            "content": [{"type": "text", "text": json.dumps(SUMMARY)}]})
    assert alert_triage.triage(EVENT)["headline"] == SUMMARY["headline"]
    fmt = sent["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert set(fmt["schema"]["required"]) == {"headline", "what_happened", "impact",
                                              "likely_fix"}
