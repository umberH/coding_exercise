"""Per-decision audit record for CareRoute.

Per PROBLEM_STATEMENT.md: "Audit record per decision: input hash, provider
version, policy version, reason." Built only from already-redacted text and
an already-computed classification/route - there is no raw-text field on
this model and no parameter that accepts one, so there is no path for PII
to reach an audit record by construction, not by caller discipline alone.
"""

import hashlib
from typing import Final

from pydantic import BaseModel

from careroute.policy import Route, RouteDecision
from careroute.schema import ClassificationResult

PROVIDER_VERSION: Final[str] = "rules-v1"
POLICY_VERSION: Final[str] = "policy-v1"


class AuditInputs(BaseModel):
    """Bundles build_audit_record's inputs under this project's 3-argument
    function-signature limit (pyproject.toml's `PLR0913`/`max-args`)."""

    redacted_text: str
    provider_name: str
    classification: ClassificationResult
    route_decision: RouteDecision


class AuditRecord(BaseModel):
    input_hash: str
    provider_name: str
    provider_version: str
    policy_version: str
    classification: ClassificationResult
    route: Route
    reason: str


def build_audit_record(inputs: AuditInputs) -> AuditRecord:
    return AuditRecord(
        input_hash=hashlib.sha256(inputs.redacted_text.encode("utf-8")).hexdigest(),
        provider_name=inputs.provider_name,
        provider_version=PROVIDER_VERSION,
        policy_version=POLICY_VERSION,
        classification=inputs.classification,
        route=inputs.route_decision.route,
        reason=inputs.route_decision.reason,
    )
