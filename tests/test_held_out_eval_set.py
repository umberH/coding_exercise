"""Structural guards on careroute/held_out_eval_set.py, mirroring
tests/test_golden_set.py's guards on the regression fixture.
"""

from careroute.held_out_eval_set import HELD_OUT_CASES

_RISK_FLAG_NAMES = ("hardship", "vulnerability", "scam")

_TRIGGER_WORDS = (
    "hardship",
    "struggl",
    "vulnerab",
    "scam",
    "fraud",
    "elderly",
    "confus",
    "otp",
    "phish",
)


def test_case_ids_are_unique() -> None:
    ids = [case.id for case in HELD_OUT_CASES]

    assert len(ids) == len(set(ids))


def test_each_risk_flag_has_at_least_two_cases() -> None:
    counts = {flag: 0 for flag in _RISK_FLAG_NAMES}
    for case in HELD_OUT_CASES:
        for flag in _RISK_FLAG_NAMES:
            if getattr(case, f"expected_{flag}"):
                counts[flag] += 1

    under_represented = {flag: count for flag, count in counts.items() if count < 2}
    assert not under_represented, under_represented


def test_each_case_sets_exactly_one_risk_flag() -> None:
    for case in HELD_OUT_CASES:
        flags = [getattr(case, f"expected_{flag}") for flag in _RISK_FLAG_NAMES]
        assert sum(flags) == 1, case.id


def test_cases_avoid_the_literal_trigger_words_rules_patterns_key_on() -> None:
    """The point of this set is to test generalization beyond the patterns
    `careroute/providers/rules.py` was written against - a case that uses one
    of those literal words isn't testing that."""
    offenders = [
        case.id
        for case in HELD_OUT_CASES
        if any(word in case.text.lower() for word in _TRIGGER_WORDS)
    ]
    assert not offenders
