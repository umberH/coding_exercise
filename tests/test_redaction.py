"""Red-first tests for CareRoute's pre-classification PII redaction step.

Assumed module under test (does not exist yet):

    careroute/redaction.py
        REDACTED_CARD: str          # "[REDACTED_CARD]"
        REDACTED_BSB_ACCOUNT: str   # "[REDACTED_BSB_ACCOUNT]"
        REDACTED_TFN: str           # "[REDACTED_TFN]"
        REDACTED_PHONE: str         # "[REDACTED_PHONE]"
        REDACTED_EMAIL: str         # "[REDACTED_EMAIL]"

        def redact(text: str) -> str: ...

Per PROBLEM_STATEMENT.md, `redact` runs "before any model call or log" -
it is independent of (and strictly precedes) classification, which is why
it is tested here on its own rather than through
`careroute.providers.rules.classify`.

Scope note: PROBLEM_STATEMENT.md's named PII list for this step is card,
BSB/account, TFN, phone, email. `tests/golden_set.py` also declares
addresses (e.g. "42 Wattle Street") and names as `pii_substrings`, but
those are used there for a *different* test (the classifier's own
output-non-leakage check in tests/test_rules_provider.py) and address/name
are not in PROBLEM_STATEMENT.md's explicit list for this redaction step.
This file deliberately does not assert either way whether `redact` touches
addresses or names - see the report for this being flagged as an open
ambiguity rather than guessed at.

Each PII-bearing case wraps the raw value in a realistic carrier sentence
so a single test can assert both halves of the 0-leakage criterion: the
raw value is gone, and the surrounding non-PII text is preserved exactly.
"""

import pytest

from careroute.redaction import (
    REDACTED_BSB_ACCOUNT,
    REDACTED_CARD,
    REDACTED_EMAIL,
    REDACTED_PHONE,
    REDACTED_TFN,
    redact,
)
from golden_set import GOLDEN_CASES

_CASES_BY_ID = {case.id: case for case in GOLDEN_CASES}

# ---------------------------------------------------------------------------
# REQ-PII-01: card numbers, in every plausible separator format, must never
# appear in redact()'s output.
# ---------------------------------------------------------------------------

_CARD_VARIANTS = (
    pytest.param("4111 1111 1111 1111", id="spaces"),
    pytest.param("4111-1111-1111-1111", id="dashes"),
    pytest.param("4111111111111111", id="no_separator"),
)


@pytest.mark.parametrize("card", _CARD_VARIANTS)
def test_redact_card_number_replaced_in_every_separator_format(card: str) -> None:
    text = f"My card number is {card}, please block it."

    result = redact(text)

    assert card not in result
    assert result == f"My card number is {REDACTED_CARD}, please block it."


# ---------------------------------------------------------------------------
# REQ-PII-04: phone numbers - AU mobile in every separator format, plus the
# +61 international-code variant - must never appear in the output.
# ---------------------------------------------------------------------------

_PHONE_VARIANTS = (
    pytest.param("0412 345 678", id="mobile_spaced"),
    pytest.param("0412345678", id="mobile_no_separator"),
    pytest.param("0412-345-678", id="mobile_dashed"),
    pytest.param("+61 412 345 678", id="international_plus61"),
)


@pytest.mark.parametrize("phone", _PHONE_VARIANTS)
def test_redact_phone_number_replaced_in_every_format(phone: str) -> None:
    text = f"Please call me on {phone} after 5pm."

    result = redact(text)

    assert phone not in result
    assert result == f"Please call me on {REDACTED_PHONE} after 5pm."


# ---------------------------------------------------------------------------
# REQ-PII-05: email addresses, including a plus-addressed/subdomain variant,
# must never appear in the output.
# ---------------------------------------------------------------------------

_EMAIL_VARIANTS = (
    pytest.param("jane.doe@example.com", id="simple"),
    pytest.param("jane.doe+alerts@mail.example.co.uk", id="plus_address_subdomain"),
)


@pytest.mark.parametrize("email", _EMAIL_VARIANTS)
def test_redact_email_replaced_in_every_format(email: str) -> None:
    text = f"You can reach me at {email} anytime."

    result = redact(text)

    assert email not in result
    assert result == f"You can reach me at {REDACTED_EMAIL} anytime."


# ---------------------------------------------------------------------------
# REQ-PII-03: Australian Tax File Numbers, in every plausible separator
# format, must never appear in the output.
# ---------------------------------------------------------------------------

_TFN_VARIANTS = (
    pytest.param("123 456 789", id="spaces"),
    pytest.param("123-456-789", id="dashes"),
    pytest.param("123456789", id="no_separator"),
)


@pytest.mark.parametrize("tfn", _TFN_VARIANTS)
def test_redact_tfn_replaced_in_every_format(tfn: str) -> None:
    text = f"My TFN is {tfn} if you need it for the hardship form."

    result = redact(text)

    assert tfn not in result
    assert result == f"My TFN is {REDACTED_TFN} if you need it for the hardship form."


# ---------------------------------------------------------------------------
# REQ-PII-02: BSB numbers (dashed and plain 6-digit) must never appear in
# the output, whether standalone or alongside a distinct account number.
# ---------------------------------------------------------------------------

_BSB_VARIANTS = (
    pytest.param("062-000", id="dashed"),
    pytest.param("062000", id="no_separator"),
)


@pytest.mark.parametrize("bsb", _BSB_VARIANTS)
def test_redact_bsb_replaced_in_every_format(bsb: str) -> None:
    text = f"Set up the new payee with BSB {bsb} please."

    result = redact(text)

    assert bsb not in result
    assert result == f"Set up the new payee with BSB {REDACTED_BSB_ACCOUNT} please."


def test_redact_bsb_and_account_number_both_replaced() -> None:
    # An 8-digit account number is used deliberately (not 9 digits), so
    # this case can't be confused with - or accidentally validate against
    # - the 9-digit TFN format tested above.
    text = "Please transfer to BSB 062-000 account 12345678 as discussed."

    result = redact(text)

    assert "062-000" not in result
    assert "12345678" not in result
    assert result == (
        f"Please transfer to BSB {REDACTED_BSB_ACCOUNT} account "
        f"{REDACTED_BSB_ACCOUNT} as discussed."
    )


# ---------------------------------------------------------------------------
# REQ-PII-02a: an account number must be redacted whenever it sits near an
# account-context keyword ("account"/"acct"), regardless of exact word
# adjacency or intervening punctuation. A fixed-width lookbehind for the
# literal substring "account " (requiring the keyword immediately before
# the digits, with exactly one space and no other words/punctuation
# between them) is NOT sufficient to satisfy this - these cases reproduce
# real leaks found in review where the keyword is present in the message
# but not immediately adjacent to the digit run.
#
# All three variants below use an 8-digit number so they can't be
# confused with the 6-digit BSB or 9-digit TFN formats tested elsewhere.
# ---------------------------------------------------------------------------


def test_redact_account_number_redacted_when_keyword_two_words_away() -> None:
    # "account" is separated from the digit run by "number is" (two more
    # words), not immediately adjacent to it.
    text = "My account number is 87654321, please check it."

    result = redact(text)

    assert "87654321" not in result
    assert result == f"My account number is {REDACTED_BSB_ACCOUNT}, please check it."


def test_redact_account_number_redacted_when_keyword_punctuation_separated() -> None:
    # Punctuation ("is:") between the keyword and the digit run breaks a
    # literal "account " adjacency match even though a human reader would
    # unambiguously read this as an account number.
    text = "my account is: 12345678"

    result = redact(text)

    assert "12345678" not in result
    assert result == f"my account is: {REDACTED_BSB_ACCOUNT}"


def test_redact_account_number_redacted_near_abbreviated_keyword_acct() -> None:
    # "acct" is a common abbreviation for "account" in the same
    # account-context-keyword family; a redactor keyed on the literal word
    # "account" alone misses it.
    text = "For the refund, use acct 12345678 thanks."

    result = redact(text)

    assert "12345678" not in result
    assert result == f"For the refund, use acct {REDACTED_BSB_ACCOUNT} thanks."


# ---------------------------------------------------------------------------
# REQ-PII-02a (continued): two independent review rounds found the SAME
# underlying bug in two different forms. Round 1: the keyword gate matched
# only the literal word "account" with a fixed-width adjacency lookbehind,
# missing "acct X" / "account number is X". That was fixed by widening to
# the keyword-window regex above (test_redact_account_number_redacted_*).
# Round 2 immediately found the same class of bug again: the keyword set
# itself only covers the literal words "account"/"acct", so realistic AU-
# banking abbreviations - "A/C", "a/c", "Acc", "acc no.", "acc:", "a.c." -
# still leak the raw digit run, because none of them contain "account" or
# "acct" as a matched word. This block enumerates that whole family of
# abbreviations in one pass instead of one regression at a time, so the bug
# class can't resurface a third time case-by-case.
#
# Every variant uses an 8-digit number, consistent with the convention
# above (distinct from the 6-digit BSB / 9-digit TFN / 16-digit card
# formats), and asserts both that the digits are gone and that the
# surrounding keyword text is preserved exactly.
# ---------------------------------------------------------------------------

_ACCOUNT_KEYWORD_ABBREVIATION_VARIANTS = (
    pytest.param("A/C", "87654321", id="slash_ac_upper"),
    pytest.param("a/c", "12345678", id="slash_ac_lower"),
    pytest.param("Acc", "12345678", id="acc_bare"),
    pytest.param("acc no.", "87654321", id="acc_no_dot"),
    pytest.param("Account No.", "87654321", id="account_no_dot_already_fixed_regression"),
    pytest.param("acc:", "12345678", id="acc_colon"),
    pytest.param("a.c.", "12345678", id="dotted_ac"),
)


@pytest.mark.parametrize(
    ("keyword_phrase", "account_number"), _ACCOUNT_KEYWORD_ABBREVIATION_VARIANTS
)
def test_redact_account_number_redacted_for_au_banking_keyword_abbreviation(
    keyword_phrase: str, account_number: str
) -> None:
    text = f"Please use {keyword_phrase} {account_number} for the refund."

    result = redact(text)

    assert account_number not in result
    assert result == f"Please use {keyword_phrase} {REDACTED_BSB_ACCOUNT} for the refund."


# ---------------------------------------------------------------------------
# REQ-PII-02a (round 3): the same bug class resurfaced a third time. Round 2
# fixed the "a/c" / "a.c." separator-joined forms above, but only for the
# case where the separator sits flush against both the "a" and the "c" with
# no intervening whitespace. In practice people type (and autocorrect
# introduces) stray spaces around the separator - "a / c", "a /c", "a/ c" -
# and the "." separator gets the same treatment. None of these have
# whitespace inside the matched span, because the keyword regex requires
# the separator character immediately adjacent to both "a" and "c" with no
# `\s*` tolerance; every one of these realistic phrasings therefore leaked
# the raw digit run before this fix.
#
# Bounded whitespace tolerance (not unbounded, so it can't be made to reach
# across unrelated text) around the separator is the one remaining widening
# this round makes; per the reviewer's explicit instruction, synonym/keyword
# widening stops here (see the xfail case immediately below this block for
# the deliberately-out-of-scope boundary that documents that stop).
#
# Every variant uses an 8-digit number, consistent with the file's
# convention (distinct from the 6-digit BSB / 9-digit TFN / 16-digit card
# formats).
# ---------------------------------------------------------------------------

_ACCOUNT_KEYWORD_SEPARATOR_WHITESPACE_VARIANTS = (
    # Covers both "spaces on both sides of the separator" AND "mixed case"
    # in a single case, since neither dimension interacts with the other.
    pytest.param("A / C", "12345678", id="slash_spaced_both_sides_mixed_case"),
    pytest.param("a /c", "87654321", id="slash_space_before_separator_only"),
    pytest.param("a/ c", "12345678", id="slash_space_after_separator_only"),
    pytest.param("a . c", "87654321", id="dot_spaced_both_sides"),
)


@pytest.mark.parametrize(
    ("keyword_phrase", "account_number"),
    _ACCOUNT_KEYWORD_SEPARATOR_WHITESPACE_VARIANTS,
)
def test_redact_account_number_redacted_for_keyword_with_whitespace_around_separator(
    keyword_phrase: str, account_number: str
) -> None:
    text = f"Please use {keyword_phrase} {account_number} for the refund."

    result = redact(text)

    assert account_number not in result
    assert result == f"Please use {keyword_phrase} {REDACTED_BSB_ACCOUNT} for the refund."


@pytest.mark.xfail(
    strict=True,
    reason=(
        "REQ-PII-02a: 'accnt' is a genuinely non-standard account-reference "
        "abbreviation (distinct from the already-covered 'acct'/'acc' family "
        "and from the separator-joined 'a/c'/'a.c.' family) that this "
        "iteration-1 rules-based keyword gate does not recognise. Per the "
        "reviewer's round-3 decision, synonym widening stops after the "
        "bounded separator-whitespace fix above; this is recorded as a "
        "known, deliberate iteration-1 boundary (mirroring "
        "hardship_multilingual_known_limitation in tests/golden_set.py) "
        "rather than chased indefinitely. An LLM-based provider is expected "
        "to catch this; the rules provider is not held to it."
    ),
)
def test_redact_account_number_not_redacted_for_nonstandard_accnt_abbreviation() -> None:
    text = "Please use accnt 12345678 for the refund."

    result = redact(text)

    assert "12345678" not in result


def test_redact_does_not_treat_account_length_digit_run_as_account_number_without_keyword() -> None:
    # An 8-digit digit run - the same length as every account number
    # redacted above - with no account-context keyword anywhere in the gap
    # window must NOT be redacted. This is the boundary for REQ-PII-02a's
    # keyword gate specifically: it documents that the keyword, not the
    # digit length, is what triggers account-number redaction. It's a
    # distinct case from test_redact_does_not_touch_a_short_non_pii_
    # reference_number below (which uses a 5-digit number precisely to
    # rule out length-based confusion with BSB/TFN/card); this one instead
    # rules out the keyword gate over-firing on account-length digits.
    text = "Your file reference is 87654321, nothing further needed."

    assert redact(text) == text


# ---------------------------------------------------------------------------
# REQ-PII-07: text with no PII at all must pass through byte-for-byte
# unchanged. Reuses golden_set.py cases rather than inventing new sample
# text, per the fixture's own stated purpose.
# ---------------------------------------------------------------------------

_NO_PII_CASE_IDS = (
    "routine_query_balance",
    "other_uncategorisable",
    "complaint_fee_dispute",
)


@pytest.mark.parametrize(
    "case_id", [pytest.param(case_id, id=case_id) for case_id in _NO_PII_CASE_IDS]
)
def test_redact_passes_through_text_with_no_pii_unchanged(case_id: str) -> None:
    case = _CASES_BY_ID[case_id]
    assert not case.pii_substrings, "fixture case unexpectedly declares PII"

    assert redact(case.text) == case.text


# ---------------------------------------------------------------------------
# REQ-PII-09 / REQ-PII-06: a single message carrying several distinct PII
# types must have every one of them redacted, while the non-PII text around
# them survives exactly. Reuses the golden_set.py case built for this.
# ---------------------------------------------------------------------------

_MULTI_PII_CASE_ID = "scam_card_compromise_with_pii"


def test_redact_replaces_every_distinct_pii_type_in_one_message() -> None:
    case = _CASES_BY_ID[_MULTI_PII_CASE_ID]

    result = redact(case.text)

    for pii_substring in case.pii_substrings:
        assert pii_substring not in result
    assert REDACTED_CARD in result
    assert REDACTED_PHONE in result
    assert REDACTED_EMAIL in result


def test_redact_preserves_non_pii_text_around_redacted_spans() -> None:
    case = _CASES_BY_ID[_MULTI_PII_CASE_ID]

    result = redact(case.text)

    assert result.startswith(
        "Someone rang claiming to be from the bank's security team and "
        "talked me into confirming my full card number "
    )
    assert "I think they've already used it. Please call me on" in result
    assert "or email" in result
    assert result.endswith("to sort this out.")


# ---------------------------------------------------------------------------
# REQ-PII-08: determinism - the same input text must redact identically on
# every call, across every PII type covered above.
# ---------------------------------------------------------------------------

_DETERMINISM_TEXTS = (
    pytest.param("My card number is 4111 1111 1111 1111, please block it.", id="card"),
    pytest.param("Please call me on 0412 345 678 after 5pm.", id="phone"),
    pytest.param("You can reach me at jane.doe@example.com anytime.", id="email"),
    pytest.param("My TFN is 123 456 789 if you need it for the form.", id="tfn"),
    pytest.param(
        "Please transfer to BSB 062-000 account 12345678 as discussed.",
        id="bsb_account",
    ),
)


@pytest.mark.parametrize("text", _DETERMINISM_TEXTS)
def test_redact_is_deterministic_across_repeated_calls(text: str) -> None:
    assert redact(text) == redact(text)


# ---------------------------------------------------------------------------
# REQ-PII-10: boundary cases - PII at the very start/end of the string, and
# PII directly adjacent to punctuation with no separating space.
# ---------------------------------------------------------------------------


def test_redact_pii_at_start_of_string() -> None:
    text = "jane.doe@example.com is where you can reach me."

    result = redact(text)

    assert "jane.doe@example.com" not in result
    assert result == f"{REDACTED_EMAIL} is where you can reach me."


def test_redact_pii_at_end_of_string() -> None:
    text = "Please call me on 0412345678"

    result = redact(text)

    assert "0412345678" not in result
    assert result == f"Please call me on {REDACTED_PHONE}"


def test_redact_pii_immediately_adjacent_to_punctuation() -> None:
    text = "My card 4111111111111111, please cancel it."

    result = redact(text)

    assert "4111111111111111" not in result
    assert result == f"My card {REDACTED_CARD}, please cancel it."


# ---------------------------------------------------------------------------
# REQ-PII-11: a realistic false-positive risk - a short numeric reference
# that is NOT any of the covered PII types - must be left untouched.
#
# A 5-digit reference number is distinct by length from every AU format
# this module targets (card=16, BSB=6, TFN=9, phone=8/10 digits), so a
# format-driven redactor has no legitimate reason to match it. This is
# asserted as a real requirement, not softened to xfail: over-redacting a
# case/reference number a bank officer needs in order to action the
# request would actively hurt triage. PROBLEM_STATEMENT.md's "favour
# recall" bias is stated for the hardship/vulnerability/scam risk flags,
# not for redaction scope, so it does not license over-redaction here.
# ---------------------------------------------------------------------------


def test_redact_does_not_touch_a_short_non_pii_reference_number() -> None:
    text = "Your complaint reference number is 48213, we'll follow up soon."

    assert redact(text) == text
