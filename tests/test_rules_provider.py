"""Red-first tests for the CareRoute offline rules-based classification
provider.

Assumed module under test (does not exist yet):

    careroute/providers/rules.py
        def classify(text: str) -> careroute.schema.ClassificationResult: ...

`classify` must be a pure, deterministic, offline function: given the same
raw message text it always returns the same ClassificationResult, with no
network access and no dependency on a live LLM. All expectations here come
from the shared golden set in tests/golden_set.py rather than bespoke
per-test sample data.
"""

import pytest

from careroute.providers.rules import classify
from golden_set import (
    GOLDEN_CASES,
    PII_CASE_IDS,
    RISK_FLAGGED_CASE_IDS,
    URGENCY_ORDER,
)

_PROVIDER = "rules"
_CASES_BY_ID = {case.id: case for case in GOLDEN_CASES}
_RISK_FLAGGED_CASES = [_CASES_BY_ID[case_id] for case_id in sorted(RISK_FLAGGED_CASE_IDS)]
_PII_CASES = [_CASES_BY_ID[case_id] for case_id in sorted(PII_CASE_IDS)]


def _as_params(cases):
    """Wrap each case in pytest.param, xfailing the ones this provider is
    documented not to handle yet (see GoldenCase.xfail_providers) instead of
    asserting the wrong label.
    """
    params = []
    for case in cases:
        marks = []
        if _PROVIDER in case.xfail_providers:
            marks.append(pytest.mark.xfail(reason=case.rationale, strict=False))
        params.append(pytest.param(case, id=case.id, marks=marks))
    return params


@pytest.mark.parametrize("case", _as_params(GOLDEN_CASES))
def test_classify_matches_golden_case(case):
    """The rules provider must assign the expected category and risk flags
    for every golden-set case: the seven per-category happy paths, implicit
    hardship with no literal keyword, a self-deprecating hardship-sounding
    phrase that must still raise the flag, and a prompt-injection attempt
    embedded in the message that must NOT change the outcome it tries to
    force.
    """
    result = classify(case.text)

    assert result.category == case.expected_category
    assert result.risk_flags.hardship == case.expected_hardship
    assert result.risk_flags.vulnerability == case.expected_vulnerability
    assert result.risk_flags.scam == case.expected_scam


@pytest.mark.parametrize("case", _as_params(_RISK_FLAGGED_CASES))
def test_urgency_meets_the_golden_case_minimum(case):
    """Per policy, any risk flag routes to the specialist queue, so urgency
    must never fall below each case's documented minimum - e.g. a scam with
    live account access must clear "high", not just clear "low" the way a
    merely-flagged case would.
    """
    result = classify(case.text)

    assert URGENCY_ORDER.index(result.urgency) >= URGENCY_ORDER.index(case.expected_min_urgency)


@pytest.mark.parametrize("case", _as_params(_PII_CASES))
def test_classify_output_never_echoes_input_pii(case):
    """The classification result must never contain the raw PII substrings
    present in the input message - this is the 0-PII-leakage success
    criterion applied to the classifier's own output.
    """
    result = classify(case.text)

    serialized = str(result.model_dump())
    for pii_substring in case.pii_substrings:
        assert pii_substring not in serialized
