"""Structural guards on the golden-set fixture itself.

These tests don't exercise `careroute` - they check that `tests/golden_set.py`
is internally consistent, so authoring mistakes (a duplicate id, an
undeclared PII substring, a category that violates the documented
precedence policy) are caught immediately instead of surfacing later as a
confusing classifier test failure.
"""

import re

from golden_set import CATEGORY_PRECEDENCE, GOLDEN_CASES, URGENCY_ORDER

_DIGIT_RUN_OR_AT_SIGN = re.compile(r"\d{2,}|@")

_RISK_FLAG_NAMES = ("scam", "vulnerability", "hardship")


def _true_flags(case):
    flags = {
        "scam": case.expected_scam,
        "vulnerability": case.expected_vulnerability,
        "hardship": case.expected_hardship,
    }
    return {name for name in _RISK_FLAG_NAMES if flags[name]}


def test_case_ids_are_unique():
    ids = [case.id for case in GOLDEN_CASES]

    assert len(ids) == len(set(ids))


def test_expected_category_is_allowed():
    for case in GOLDEN_CASES:
        assert case.expected_category in CATEGORY_PRECEDENCE, case.id


def test_each_category_has_at_least_two_cases():
    counts = {category: 0 for category in CATEGORY_PRECEDENCE}
    for case in GOLDEN_CASES:
        counts[case.expected_category] += 1

    under_represented = {category: count for category, count in counts.items() if count < 2}
    assert not under_represented, under_represented


def test_digit_run_or_at_sign_requires_declared_pii():
    offenders = [
        case.id
        for case in GOLDEN_CASES
        if _DIGIT_RUN_OR_AT_SIGN.search(case.text) and not case.pii_substrings
    ]
    assert not offenders


def test_expected_category_follows_precedence_policy():
    violations = []
    for case in GOLDEN_CASES:
        true_flags = _true_flags(case)
        if not true_flags:
            continue

        expected = next(name for name in CATEGORY_PRECEDENCE if name in true_flags)
        if case.expected_category != expected:
            violations.append((case.id, case.expected_category, expected))

    assert not violations


def test_risk_flagged_cases_do_not_claim_low_urgency():
    offenders = [
        case.id for case in GOLDEN_CASES if _true_flags(case) and case.expected_min_urgency == "low"
    ]
    assert not offenders


def test_expected_min_urgency_is_a_known_level():
    for case in GOLDEN_CASES:
        assert case.expected_min_urgency in URGENCY_ORDER, case.id
