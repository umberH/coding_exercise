"""Tests for the end-to-end triage pipeline (careroute/pipeline.py):
redact -> classify -> decide -> audit, in that order.
"""

import hashlib

from careroute.pipeline import triage
from careroute.policy import Route
from careroute.redaction import redact


def test_triage_audit_record_never_contains_raw_pii_substrings() -> None:
    raw = "My card is 4111 1111 1111 1111, please block it."

    result = triage(raw)

    dumped = result.audit.model_dump_json()
    assert "4111 1111 1111 1111" not in dumped
    assert "4111111111111111" not in dumped


def test_triage_audit_input_hash_matches_hash_of_redacted_not_raw_text() -> None:
    raw = "My email is jane.doe@example.com, please update my address."

    result = triage(raw)

    assert result.audit.input_hash == hashlib.sha256(redact(raw).encode("utf-8")).hexdigest()
    assert result.audit.input_hash != hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_triage_routes_a_risk_flagged_message_to_specialist_queue() -> None:
    message = (
        "Someone rang pretending to be from the bank and talked me into giving "
        "my one-time code, I think they've already taken money from my account."
    )

    result = triage(message)

    assert result.classification.risk_flags.scam is True
    assert result.route_decision.route is Route.SPECIALIST_QUEUE


def test_triage_routes_a_low_confidence_non_risk_message_to_human_review() -> None:
    result = triage("asdkjhasdkjh qweoiuqwe random unclassifiable text")

    assert result.route_decision.route is Route.HUMAN_REVIEW
