"""Deterministic routing policy for CareRoute.

Per PROBLEM_STATEMENT.md: "any risk flag -> specialist queue; low
confidence -> human review." `decide` is a pure function, classification
result in, `RouteDecision` out - no I/O, no model call, no clock, no
randomness - so the same `ClassificationResult` always yields the same
route, independent of when or how often it's evaluated.

Per DESIGN.md: risk flags take precedence over confidence. A low-confidence
risk flag still routes to the specialist queue, not human review, because
the risk signal is the stronger prior.
"""

from enum import Enum
from typing import Final

from pydantic import BaseModel

from careroute.schema import ClassificationResult

CONFIDENCE_THRESHOLD: Final[float] = 0.7


class Route(str, Enum):
    SPECIALIST_QUEUE = "specialist_queue"
    HUMAN_REVIEW = "human_review"
    GENERAL_QUEUE = "general_queue"


class RouteDecision(BaseModel):
    route: Route
    reason: str


def _risk_reason(result: ClassificationResult) -> str:
    flags = result.risk_flags
    fired = [
        name
        for name, value in (
            ("scam", flags.scam),
            ("vulnerability", flags.vulnerability),
            ("hardship", flags.hardship),
        )
        if value
    ]
    return f"risk flag(s) set: {', '.join(fired)}"


def decide(result: ClassificationResult) -> RouteDecision:
    flags = result.risk_flags
    if flags.scam or flags.vulnerability or flags.hardship:
        return RouteDecision(route=Route.SPECIALIST_QUEUE, reason=_risk_reason(result))

    if result.confidence < CONFIDENCE_THRESHOLD:
        reason = f"confidence {result.confidence:.2f} below threshold {CONFIDENCE_THRESHOLD:.2f}"
        return RouteDecision(route=Route.HUMAN_REVIEW, reason=reason)

    reason = f"confidence {result.confidence:.2f} at/above threshold, no risk flag"
    return RouteDecision(route=Route.GENERAL_QUEUE, reason=reason)
