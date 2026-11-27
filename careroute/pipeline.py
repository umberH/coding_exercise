"""End-to-end triage pipeline: redact -> classify -> decide -> audit.

One function, `triage`, that enforces the order PROBLEM_STATEMENT.md
requires: redaction completes before any text reaches a provider, a log, or
the audit record, and policy only ever sees the already-computed
`ClassificationResult` - never raw or redacted text - so it can't
accidentally depend on data it has no business using.
"""

from dataclasses import dataclass

from careroute.audit import AuditInputs, AuditRecord, build_audit_record
from careroute.policy import RouteDecision, decide
from careroute.providers.rules import classify
from careroute.redaction import redact
from careroute.schema import ClassificationResult

PROVIDER_NAME = "rules"


@dataclass(frozen=True)
class TriageResult:
    classification: ClassificationResult
    route_decision: RouteDecision
    audit: AuditRecord


def triage(message: str) -> TriageResult:
    redacted = redact(message)
    classification = classify(redacted)
    route_decision = decide(classification)
    audit = build_audit_record(
        AuditInputs(
            redacted_text=redacted,
            provider_name=PROVIDER_NAME,
            classification=classification,
            route_decision=route_decision,
        )
    )
    return TriageResult(classification=classification, route_decision=route_decision, audit=audit)
