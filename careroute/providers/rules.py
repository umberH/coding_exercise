"""Offline, deterministic rules-based classification provider.

Iteration 1 implementation of the classifier interface (`classify(text) ->
ClassificationResult`) that an iteration-2 LLM provider will later sit behind
as well. Pure keyword/pattern matching - no network, no model call, no
instructions-in-the-message are ever treated as commands, which is what
keeps prompt-injection attempts embedded in `text` from changing the result.
"""

import re

from careroute.schema import Category, ClassificationResult, RiskFlags, UrgencyLevel

_HIGH_CONFIDENCE = 0.9
_LOW_CONFIDENCE = 0.4

_HARDSHIP_PATTERNS = (
    r"\bhardship\b",
    r"\bstruggl\w*",
    r"can'?t (?:afford|pay)",
    r"haven'?t been able to (?:afford|pay)",
    r"unable to (?:afford|pay)",
    r"won'?t be able to (?:make|pay|afford)",
    r"payment arrangement",
    r"los(?:t|ing) my job",
    r"\btight\b",
)

_VULNERABILITY_PATTERNS = (
    r"\belderly\b",
    r"\bvulnerab\w*",
    r"\bconfus\w*",
    r"\bforgett?ing\b",
    r"can'?t manage",
    r"on (?:his|her|their) own anymore",
    r"unwell mentally",
)

_SCAM_PATTERNS = (
    r"\bscam\w*",
    r"\bfraud\w*",
    r"\bphish\w*",
    r"pretend\w* to be",
    r"claiming to be",
    r"one-time code",
    r"\botp\b",
    r"unauthoris\w* transaction",
    r"accessed my account",
    r"taken advantage of",
    r"can'?t properly explain",
)

_COMPLAINT_PATTERNS = (
    r"\bunhappy\b",
    r"\bcomplain\w*",
    r"\brefund\w*",
    r"charged me",
    r"\bdispute\w*",
    r"hasn'?t gone through",
)

_ROUTINE_QUERY_PATTERNS = (
    r"could you (?:please )?tell me",
    r"\bbalance\b",
    r"\bstatement\b",
    r"\binterest rate\b",
    r"what time does",
)

_ACCOUNT_ADMIN_PATTERNS = (
    r"update (?:the|my) [\w\s]*address",
    r"change (?:the|my) [\w\s]*address",
    r"address on file",
    r"update my details",
    r"update (?:the|my) [\w\s]*(?:mobile|phone) number",
)

_FALLBACK_CATEGORY_PATTERNS = (
    (Category.COMPLAINT, _COMPLAINT_PATTERNS),
    (Category.ACCOUNT_ADMIN, _ACCOUNT_ADMIN_PATTERNS),
    (Category.ROUTINE_QUERY, _ROUTINE_QUERY_PATTERNS),
)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _detect_risk_flags(text: str) -> RiskFlags:
    hardship = _matches_any(text, _HARDSHIP_PATTERNS)
    vulnerability = _matches_any(text, _VULNERABILITY_PATTERNS)
    scam = _matches_any(text, _SCAM_PATTERNS)
    return RiskFlags(hardship=hardship, vulnerability=vulnerability, scam=scam)


def _risk_flag_category(risk_flags: RiskFlags) -> Category | None:
    if risk_flags.scam:
        return Category.SCAM
    if risk_flags.vulnerability:
        return Category.VULNERABILITY
    if risk_flags.hardship:
        return Category.HARDSHIP
    return None


def _detect_category(text: str, risk_flags: RiskFlags) -> Category:
    risk_category = _risk_flag_category(risk_flags)
    if risk_category is not None:
        return risk_category
    for category, patterns in _FALLBACK_CATEGORY_PATTERNS:
        if _matches_any(text, patterns):
            return category
    return Category.OTHER


def _determine_urgency(risk_flags: RiskFlags) -> UrgencyLevel:
    if risk_flags.scam:
        return UrgencyLevel.HIGH
    if risk_flags.hardship or risk_flags.vulnerability:
        return UrgencyLevel.MEDIUM
    return UrgencyLevel.LOW


def _determine_confidence(category: Category) -> float:
    return _HIGH_CONFIDENCE if category != Category.OTHER else _LOW_CONFIDENCE


def classify(text: str) -> ClassificationResult:
    risk_flags = _detect_risk_flags(text)
    category = _detect_category(text, risk_flags)
    return ClassificationResult(
        category=category,
        risk_flags=risk_flags,
        urgency=_determine_urgency(risk_flags),
        confidence=_determine_confidence(category),
    )
