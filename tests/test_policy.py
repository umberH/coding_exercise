"""Tests for the deterministic routing policy (careroute/policy.py).

Per PROBLEM_STATEMENT.md: "any risk flag -> specialist queue; low
confidence -> human review." Per DESIGN.md, risk flags take precedence over
confidence, so a low-confidence risk-flagged result must still land in the
specialist queue, not human review.
"""

import pytest

from careroute.policy import CONFIDENCE_THRESHOLD, Route, decide
from careroute.schema import Category, ClassificationResult, RiskFlags, UrgencyLevel


_NO_RISK = RiskFlags(hardship=False, vulnerability=False, scam=False)


def _result(
    category: Category, confidence: float, risk_flags: RiskFlags = _NO_RISK
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        risk_flags=risk_flags,
        urgency=UrgencyLevel.LOW,
        confidence=confidence,
    )


@pytest.mark.parametrize("flag_name", ["hardship", "vulnerability", "scam"])
def test_any_single_risk_flag_routes_to_specialist_queue(flag_name: str) -> None:
    flags = RiskFlags(**{**_NO_RISK.model_dump(), flag_name: True})
    result = _result(Category.OTHER, confidence=0.95, risk_flags=flags)

    assert decide(result).route is Route.SPECIALIST_QUEUE


def test_risk_flag_routes_to_specialist_queue_even_at_low_confidence() -> None:
    flags = RiskFlags(hardship=False, vulnerability=False, scam=True)
    result = _result(Category.SCAM, confidence=0.1, risk_flags=flags)

    assert decide(result).route is Route.SPECIALIST_QUEUE


def test_multiple_true_risk_flags_still_route_to_specialist_queue() -> None:
    flags = RiskFlags(hardship=True, vulnerability=False, scam=True)
    result = _result(Category.SCAM, confidence=0.95, risk_flags=flags)

    assert decide(result).route is Route.SPECIALIST_QUEUE


def test_no_risk_flag_and_confidence_below_threshold_routes_to_human_review() -> None:
    result = _result(Category.OTHER, confidence=CONFIDENCE_THRESHOLD - 0.01)

    assert decide(result).route is Route.HUMAN_REVIEW


def test_no_risk_flag_and_confidence_at_threshold_routes_to_general_queue() -> None:
    result = _result(Category.ROUTINE_QUERY, confidence=CONFIDENCE_THRESHOLD)

    assert decide(result).route is Route.GENERAL_QUEUE


def test_no_risk_flag_and_high_confidence_routes_to_general_queue() -> None:
    result = _result(Category.ROUTINE_QUERY, confidence=0.95)

    assert decide(result).route is Route.GENERAL_QUEUE


def test_decision_reason_is_non_empty_for_every_route() -> None:
    scam_flags = RiskFlags(hardship=False, vulnerability=False, scam=True)
    cases = (
        _result(Category.SCAM, confidence=0.95, risk_flags=scam_flags),
        _result(Category.OTHER, confidence=0.1),
        _result(Category.ROUTINE_QUERY, confidence=0.95),
    )

    for result in cases:
        assert decide(result).reason
