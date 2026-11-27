"""Tests for the per-decision audit record (careroute/audit.py).

Per PROBLEM_STATEMENT.md: "Audit record per decision: input hash, provider
version, policy version, reason." Built only from redacted text, so there
is no raw-PII path into it by construction.
"""

from careroute.audit import (
    POLICY_VERSION,
    PROVIDER_VERSION,
    AuditInputs,
    AuditRecord,
    build_audit_record,
)
from careroute.policy import Route, RouteDecision
from careroute.schema import Category, ClassificationResult, RiskFlags, UrgencyLevel

_CLASSIFICATION = ClassificationResult(
    category=Category.OTHER,
    risk_flags=RiskFlags(hardship=False, vulnerability=False, scam=False),
    urgency=UrgencyLevel.LOW,
    confidence=0.4,
)
_ROUTE_DECISION = RouteDecision(route=Route.HUMAN_REVIEW, reason="low confidence")


def _build(redacted_text: str) -> AuditRecord:
    return build_audit_record(
        AuditInputs(
            redacted_text=redacted_text,
            provider_name="rules",
            classification=_CLASSIFICATION,
            route_decision=_ROUTE_DECISION,
        )
    )


def test_build_audit_record_never_embeds_the_redacted_text_itself() -> None:
    record = _build("My card is [REDACTED_CARD].")

    assert record.input_hash
    assert "[REDACTED_CARD]" not in record.model_dump_json()


def test_build_audit_record_hash_is_deterministic_for_the_same_text() -> None:
    first = _build("Same redacted text.")
    second = _build("Same redacted text.")

    assert first.input_hash == second.input_hash


def test_build_audit_record_hash_differs_for_different_text() -> None:
    first = _build("First message.")
    second = _build("Second message.")

    assert first.input_hash != second.input_hash


def test_build_audit_record_carries_provider_and_policy_versions() -> None:
    record = _build("text")

    assert record.provider_name == "rules"
    assert record.provider_version == PROVIDER_VERSION
    assert record.policy_version == POLICY_VERSION
