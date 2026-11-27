"""Pre-classification PII redaction for CareRoute.

Per PROBLEM_STATEMENT.md: "Redact PII (card, BSB/account, TFN, phone,
email) before any model call or log." This module is that pre-processing
step. It is independent of, and runs strictly before, classification
(`careroute.providers.rules.classify`) - redaction must not depend on, or
be gated by, what category or risk flags a message would get.

Interface: a single pure function, `redact`, that returns a copy of the
input text with every detected PII span replaced by a type-labeled
placeholder token (one of the REDACTED_* constants below). Downstream code
and logs can then see *that* something was redacted and *what kind*,
without the raw value ever reaching them - this is what lets the 0-PII-
leakage success criterion be satisfied at a single choke point instead of
trusting every call site (API handler, logger, eval harness, ...) to scrub
its own output independently.

`redact` must be pure, deterministic and fully offline: same input text
always yields the same output text, with no network access, no reliance on
wall-clock time, and no randomness.
"""

import re
from collections.abc import Callable
from typing import Final

REDACTED_CARD: Final[str] = "[REDACTED_CARD]"
REDACTED_BSB_ACCOUNT: Final[str] = "[REDACTED_BSB_ACCOUNT]"
REDACTED_TFN: Final[str] = "[REDACTED_TFN]"
REDACTED_PHONE: Final[str] = "[REDACTED_PHONE]"
REDACTED_EMAIL: Final[str] = "[REDACTED_EMAIL]"

# How many non-digit characters of slack are tolerated between an
# account-context keyword ("account", "acct", "acc", "a/c", "a.c.", ...) and
# the digit run it refers to, e.g. "account number is 87654321" or "acc no.
# 87654321". Python's `re` lookbehind must be fixed-width, so it cannot
# express "the keyword, then optionally more words/punctuation" directly; a
# cap on non-digit gap characters, checked against the text *preceding* a
# candidate digit run, gets the same effect without that restriction. A run
# of digits in the gap ends the search instead of counting towards it, so
# the keyword is never credited across an unrelated earlier number.
_ACCOUNT_KEYWORD_GAP_CHARS: Final[int] = 30

# Every pattern requires a non-digit (or string edge) immediately before and
# after its full match, so a shorter pattern can never claim part of a
# longer digit run - this is what keeps card/TFN/phone/BSB mutually
# exclusive without needing to try every pattern at every position.
_CARD_RE = re.compile(r"(?<!\d)\d{4}(?:[- ]?\d{4}){3}(?!\d)")
_TFN_RE = re.compile(r"(?<!\d)\d{3}[- ]?\d{3}[- ]?\d{3}(?!\d)")
_PHONE_INTERNATIONAL_RE = re.compile(r"(?<!\d)\+61[ ]?\d{3}[ ]?\d{3}[ ]?\d{3}(?!\d)")
_PHONE_MOBILE_RE = re.compile(r"(?<!\d)0\d{3}[- ]?\d{3}[- ]?\d{3}(?!\d)")
_ACCOUNT_NUMBER_RE = re.compile(r"(?<!\d)\d{4,12}(?!\d)")
# All AU-banking account-reference abbreviations share the prefix "a" plus
# a suffix that is either a word ("ccount", "cct", "cc") or a single
# separator-joined letter ("/c", ".c", covering "a/c" and "a.c."). The
# trailing separator in "a.c." is deliberately left out of this group and
# left for `_ACCOUNT_KEYWORD_GAP_CHARS` to absorb: a `\b` placed right after
# a literal "." could never match (the text on both sides of a "." is
# typically non-word), whereas `\b` right after the shared "c" reliably
# rejects a hit inside an unrelated word (e.g. "acceptable", "accountant").
# The separator in the "a/c"/"a.c." form tolerates optional surrounding
# whitespace ("a / c", "a /c", "a/ c") since that is how people actually
# type it; the tolerance is bounded to a single `\s*` on each side of the
# separator so it can never reach across unrelated words.
_ACCOUNT_KEYWORD_GAP_RE = re.compile(
    rf"\ba(?:ccount|cct|cc|\s*[./]\s*c)\b[^\d]{{0,{_ACCOUNT_KEYWORD_GAP_CHARS}}}$",
    re.IGNORECASE,
)
_BSB_RE = re.compile(r"(?<!\d)\d{3}-\d{3}(?!\d)|(?<!\d)\d{6}(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _redact_account_numbers(text: str) -> str:
    """Replace digit runs preceded by an account-context keyword with the account placeholder."""

    def _replace(match: re.Match[str]) -> str:
        preceding_text = text[: match.start()]
        if _ACCOUNT_KEYWORD_GAP_RE.search(preceding_text):
            return REDACTED_BSB_ACCOUNT
        return match.group()

    return _ACCOUNT_NUMBER_RE.sub(_replace, text)


# Order matters: the +61 international phone must run before TFN, or TFN's
# bare 9-digit pattern claims the digits after "+61 " for itself. TFN must
# run before BSB so a 9-digit dashed TFN ("123-456-789") is claimed whole
# before BSB's shorter dashed form ("\d{3}-\d{3}") can be tried at the same
# starting position. Account numbers must also run before BSB so an 8-digit
# keyword-flagged account number isn't mistaken for BSB's bare 6-digit form.
_REDACTIONS: Final[tuple[Callable[[str], str], ...]] = (
    lambda text: _CARD_RE.sub(REDACTED_CARD, text),
    lambda text: _PHONE_INTERNATIONAL_RE.sub(REDACTED_PHONE, text),
    lambda text: _PHONE_MOBILE_RE.sub(REDACTED_PHONE, text),
    lambda text: _TFN_RE.sub(REDACTED_TFN, text),
    _redact_account_numbers,
    lambda text: _BSB_RE.sub(REDACTED_BSB_ACCOUNT, text),
    lambda text: _EMAIL_RE.sub(REDACTED_EMAIL, text),
)


def redact(text: str) -> str:
    """Return `text` with every detected PII span replaced by the matching
    REDACTED_* placeholder for its type (card, BSB/account, TFN, phone,
    email - per PROBLEM_STATEMENT.md's named PII types for this step).

    Non-PII characters, including whitespace and punctuation outside a
    detected PII span, must be preserved unchanged.
    """
    for redactor in _REDACTIONS:
        text = redactor(text)
    return text
