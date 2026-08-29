"""Turn a raw pipeline failure into something worth reading at 7am.

A traceback answers "what threw". It does not answer the three questions actually being
asked when an alert arrives: what broke, does it matter, and what do I do. This module
asks Claude those three questions and puts the answers at the top of the email, with the
technical detail kept underneath rather than thrown away.

Three constraints shape everything here, all of them consequences of running *inside* the
failure path:

1. **It may never suppress an alert.** Every path returns None rather than raising, and
   the caller falls back to the plain-text email. An alert that fails to send because its
   summariser broke is strictly worse than an ugly alert.
2. **No third-party dependency.** The Anthropic SDK is a better API, but a failed or
   conflicting install in this module would take out alerting itself — the one thing that
   must keep working when everything else is broken. `urllib` ships with Python and cannot
   be uninstalled.
3. **A hard timeout.** The callback holds an Airflow task slot while it runs. A hung HTTP
   call must cost seconds, not the run.

Secrets are stripped before anything leaves the machine: a traceback can carry a
connection string or a token, and this is the one place in the pipeline that sends error
text to a third party.

Usage:
  python -m src.alert_triage --latest        # triage the most recent recorded failure
  python -m src.alert_triage --dry-run       # show the prompt, call nothing
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# Configurable so the model can be changed without a code edit — this is the kind of
# setting that wants changing at 7am, not at review time.
MODEL = os.getenv("ALERT_TRIAGE_MODEL", "claude-sonnet-5")

# Seconds. Deliberately short: this runs while an Airflow slot is held, and a summary that
# arrives late is worth less than the email it is delaying.
TIMEOUT = int(os.getenv("ALERT_TRIAGE_TIMEOUT", "25"))

# THINKING TOKENS COME OUT OF THIS BUDGET, AND THAT IS WHY 900 WAS NOT ENOUGH.
#
# Sonnet 5 runs adaptive thinking when `thinking` is omitted — it is not opt-in the way it
# was on older models. Measured on a real alert: 828 output tokens, of which 400 were
# thinking. The JSON had 428 tokens to fit in and 72 to spare. It fits most of the time,
# which is the worst possible failure mode: on 29 August it did not, the reply was truncated
# mid-object, `_parse` returned None and the email lost its summary.
#
# 2000 is roughly three times the observed need. The cost is a rounding error — a truncated
# summary costs the whole point of the feature.
MAX_TOKENS = 2000

# The reply must conform to this or the API does not return it. `output_config.format`
# replaces the older approach of asking for JSON in the prompt and hoping: the prompt still
# describes what each field should contain, but the SHAPE is now enforced server-side rather
# than validated after the fact by `_parse`.
#
# `_parse` stays. Structured output guarantees conformance only when generation COMPLETES —
# a truncated response is still truncated — so the tolerant parser remains the backstop and
# `stop_reason` is now reported when it is the cause.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "what_happened": {"type": "string"},
        "impact": {"type": "string"},
        "likely_fix": {"type": "string"},
    },
    "required": ["headline", "what_happened", "impact", "likely_fix"],
    "additionalProperties": False,
}

# Tracebacks are long and the useful part is the end. Bounded so a runaway log cannot turn
# one alert into a large request.
MAX_TRACEBACK_CHARS = 6000

# Environment variables whose *values* must never leave the machine. Matched by value, not
# by name, because a traceback leaks the secret itself, not the variable that held it.
SECRET_ENV_VARS = (
    "ANTHROPIC_API_KEY", "CFBD_API_KEY", "DATABRICKS_TOKEN", "PG_PASSWORD",
    "ALERT_SMTP_PASSWORD", "AIRFLOW_FERNET_KEY", "AIRFLOW_JWT_SECRET",
    "SERVING_PG_PASSWORD", "CFDB_READ_PASSWORD",
)

SYSTEM_PROMPT = """\
You are triaging a failure in cfdb, a college football analytics pipeline, for its sole \
maintainer — a senior BI/analytics engineer who knows SQL and dbt well and is comfortable \
but not expert in Python, Airflow and Docker.

The architecture, so your advice is concrete:
- CFBD REST API -> Python ingestion -> immutable raw JSON files on disk -> loaded into
  Postgres (transform warehouse) and Databricks (analytics warehouse).
- dbt builds staging -> marts -> serving models. dbt owns all transforms and data tests.
- Airflow (Docker Compose, LocalExecutor) owns scheduling and retries only. Its DAGs
  bind-mount the git working tree, so a branch checkout changes what Airflow runs.
- Marts are published over SSH to a serving Postgres on a droplet; a Streamlit site reads
  it behind Cloudflare Access.
- Betting lines are snapshotted on a schedule. A snapshot never taken is unrecoverable
  data; everything else can be re-fetched from the API or rebuilt from raw files.

Reply with ONLY a JSON object, no prose and no code fence, with exactly these keys:

  "headline":     under 70 characters. The failure in plain words, specific enough to act
                  on. Goes in the email subject. No "Error:" prefix, no DAG name — the
                  subject already carries those.
  "what_happened": 2-3 sentences. What actually went wrong and why, in plain language.
                  Name the real cause, not the symptom, when the traceback shows it.
  "impact":       2-3 sentences. What is broken now, what still works, and whether data
                  was lost. Say plainly when the answer is "nothing was lost" — that is
                  usually the most useful sentence in the email. Call out irrecoverable
                  loss only when it is genuinely irrecoverable.
  "likely_fix":   2-4 sentences, or short numbered steps. Concrete and specific: name the
                  command, file or setting. If the cause is genuinely ambiguous, say what
                  to check first and what each outcome would mean.

Be direct and specific. Do not hedge, do not restate the traceback, and do not invent
details the input does not support. If the input is too thin to diagnose, say so in
what_happened and use likely_fix to name what to look at."""


def redact(text: Optional[str]) -> Optional[str]:
    """Replace known secret values with a marker.

    Matched by value rather than by pattern: a token is unrecognisable out of context, but
    we know exactly what ours are because they are in this process's environment. Short
    values are skipped — a two-character secret would match half the traceback.
    """
    if not text:
        return text
    for name in SECRET_ENV_VARS:
        value = os.getenv(name)
        if value and len(value) >= 8:
            text = text.replace(value, f"<{name} redacted>")
    # Bearer tokens and URL credentials can arrive from libraries we do not control.
    text = re.sub(r"(://[^:/\s]+:)[^@/\s]+(@)", r"\1<redacted>\2", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}", r"\1<redacted>", text)
    return text


def build_prompt(event: Dict[str, Any]) -> str:
    """The failure, trimmed and redacted, as the user turn."""
    traceback_text = redact(event.get("traceback")) or "(no traceback captured)"
    if len(traceback_text) > MAX_TRACEBACK_CHARS:
        # Keep the tail: the raising frame and the exception are at the end.
        traceback_text = "...(earlier frames trimmed)...\n" + traceback_text[-MAX_TRACEBACK_CHARS:]

    return (
        f"DAG: {event.get('dag_id')}\n"
        f"Task: {event.get('task_id')}\n"
        f"Run: {event.get('run_id')}\n"
        f"Attempt: {event.get('try_number')}\n"
        f"Time (UTC): {event.get('at')}\n"
        f"Error: {redact(event.get('error')) or '(none recorded)'}\n\n"
        f"Traceback:\n{traceback_text}\n"
    )


def _post(payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse(text: str) -> Optional[Dict[str, str]]:
    """Pull the JSON object out of the reply, tolerating a stray fence or preamble."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, dict):
        return None
    # A partial answer is still useful, but a headline is what the subject line needs.
    if not parsed.get("headline"):
        return None
    return {k: str(v).strip() for k, v in parsed.items() if isinstance(v, (str, int, float))}


# Why the most recent triage() gave up. Read by the alerting module so a broken summariser
# is stated IN THE EMAIL rather than only in a task log nobody opens.
#
# THIS EXISTS BECAUSE THE SILENT VERSION COST US THREE WEEKS. The key in .env was rejected
# with "API key is invalid" on 21 consecutive alerts. Every one of them still sent — the
# fallback worked exactly as designed — so nothing looked broken, the plain email is a
# perfectly reasonable email, and the only trace was one stdout line inside a failing task's
# log. A degradation that hides inside a working fallback is the hardest kind to notice.
#
# Process-local module state is safe here: Airflow's LocalExecutor runs each task in its own
# process, and the value is set and read within one callback.
_unavailable_reason: Optional[str] = None


def unavailable_reason() -> Optional[str]:
    """Why the last triage() returned None, or None if it produced a summary."""
    return _unavailable_reason


def triage_model() -> str:
    """The model triage will use. A function, not the constant, so `--check` reports what a
    fresh process would actually pick up rather than what was read at import time."""
    return os.getenv("ALERT_TRIAGE_MODEL", MODEL)


def check_credentials() -> Tuple[bool, str]:
    """Probe the API key without spending tokens. Returns (ok, human explanation).

    WHY THIS IS ITS OWN CHECK. The key in .env was rejected for the entire life of this
    feature and nobody knew, because every alert still sent. `--check` reported SMTP in
    detail and never mentioned triage, so the one command whose job is "is alerting working"
    could not see the half of it that was broken.

    GET /v1/models is the cheapest authenticated call there is — no tokens, no model
    invoked. It validates CREDENTIALS, which is the failure mode that actually happened; it
    does not prove the account has quota, and it says so.

    Distinguishing 401 from 403 matters and is the whole reason to probe this endpoint
    rather than /v1/messages: /v1/models needs no workspace scoping, so `authentication_error`
    here means the key is not recognised at all, while `permission_error` would mean a real
    key pointed at the wrong workspace. Those need different fixes.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return False, "ANTHROPIC_API_KEY is not set — alerts will send without a summary"

    request = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": api_key, "anthropic-version": API_VERSION},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT):
            return True, "credentials accepted"
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:                                          # noqa: BLE001
            pass
        message = (_api_error_message(body).strip().rstrip(". ") or str(exc.reason))
        if exc.code == 401:
            return False, (f"HTTP 401 — {message}. The key is not recognised. A workspace "
                           f"ID will not help: /v1/models needs no workspace scoping, so "
                           f"this fails before any scope is checked. Mint a new key.")
        if exc.code in (403, 404):
            return False, (f"HTTP {exc.code} — {message}. The key authenticates but is not "
                           f"permitted here; check the workspace it belongs to.")
        return False, f"HTTP {exc.code} — {message}"
    except Exception as exc:                                       # noqa: BLE001
        return False, f"could not reach the API ({type(exc).__name__}: {exc})"


def _api_error_message(body: str) -> str:
    """The human sentence out of an API error body, falling back to the raw text."""
    try:
        return json.loads(body).get("error", {}).get("message", "") or body
    except Exception:                                              # noqa: BLE001
        return body


def triage(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Ask Claude to explain this failure. Returns None if it cannot, and never raises.

    None is a first-class outcome, not an error: no API key configured is the normal state
    on a fresh machine, and the caller sends the plain email instead. What it must never be
    is SILENT — see `unavailable_reason`.
    """
    global _unavailable_reason
    _unavailable_reason = None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        _unavailable_reason = "ANTHROPIC_API_KEY is not set"
        return None

    try:
        response = _post({
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": build_prompt(event)}],
            "output_config": {"format": {"type": "json_schema",
                                         "schema": RESPONSE_SCHEMA}},
        }, api_key)

        blocks = response.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        result = _parse(text)
        if result:
            result["model"] = response.get("model", MODEL)
            return result

        # NAME THE CAUSE, DO NOT JUST SAY "could not be parsed".
        #
        # That phrasing sent us looking at the parser when the real answer was in `usage`:
        # thinking had eaten the token budget and the JSON was cut off mid-object. A reason
        # that points at the wrong component is worse than a vague one.
        stop = response.get("stop_reason")
        usage = response.get("usage") or {}
        if stop == "max_tokens":
            thinking = (usage.get("output_tokens_details") or {}).get("thinking_tokens")
            _unavailable_reason = (
                f"{MODEL} hit the {MAX_TOKENS}-token limit and the reply was cut off"
                + (f" ({thinking} of it thinking)" if thinking else "")
                + " — raise MAX_TOKENS in src/alert_triage.py")
        else:
            _unavailable_reason = (
                f"{MODEL} replied but the summary could not be parsed "
                f"(stop_reason={stop}, {usage.get('output_tokens')} output tokens)")
        return None
    except urllib.error.HTTPError as exc:
        # The body carries the real reason (bad key, rate limit); the status alone does not.
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:200]
        except Exception:                                          # noqa: BLE001
            pass
        _unavailable_reason = f"HTTP {exc.code} from the Anthropic API"
        message = _api_error_message(detail).strip()
        if message:
            _unavailable_reason += f" — {message}"
        print(f"ALERT: triage unavailable (HTTP {exc.code}) {detail}")
        return None
    except Exception as exc:  # never raise from an alert path
        _unavailable_reason = f"{type(exc).__name__}: {exc}"
        print(f"ALERT: triage unavailable ({type(exc).__name__}: {exc})")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Triage a recorded failure and print the email it would produce.")
    parser.add_argument("--latest", action="store_true",
                        help="use the most recent entry in data/alerts/failures.jsonl")
    parser.add_argument("--index", type=int,
                        help="use the Nth recorded failure (0-based)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompt and exit without calling the API")
    args = parser.parse_args()

    path = Path("data") / "alerts" / "failures.jsonl"
    if not path.exists():
        print(f"No failure log at {path}")
        return 1
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    if not events:
        print("Failure log is empty")
        return 1

    event = events[args.index] if args.index is not None else events[-1]
    print(f"Failure: {event.get('dag_id')}.{event.get('task_id')} at {event.get('at')}\n")

    if args.dry_run:
        print("--- system prompt ---")
        print(SYSTEM_PROMPT)
        print("\n--- user turn ---")
        print(build_prompt(event))
        return 0

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set — triage would be skipped and the plain "
              "email sent instead.")
        return 1

    result = triage(event)
    if not result:
        print("Triage returned nothing; the plain email would be sent.")
        return 1

    # Imported here rather than at module scope: alerting imports this module, and a
    # top-level import back into it would be circular.
    from .alerting import format_email
    subject, body = format_email(event, result)
    print(f"Subject: {subject}\n")
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
