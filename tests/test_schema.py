"""Red-first tests for the CareRoute classification result schema.

Assumed module under test (does not exist yet):

    careroute/schema.py
        class Category(str, Enum):
            COMPLAINT = "complaint"
            HARDSHIP = "hardship"
            VULNERABILITY = "vulnerability"
            SCAM = "scam"
            ROUTINE_QUERY = "routine_query"
            ACCOUNT_ADMIN = "account_admin"
            OTHER = "other"

        class UrgencyLevel(str, Enum):
            LOW = "low"
            MEDIUM = "medium"
            HIGH = "high"

        class RiskFlags(BaseModel):
            hardship: bool
            vulnerability: bool
            scam: bool

        class ClassificationResult(BaseModel):
            category: Category
            risk_flags: RiskFlags
            urgency: UrgencyLevel
            confidence: float  # constrained to [0.0, 1.0]

These are pydantic models, so malformed construction is expected to raise
pydantic.ValidationError.
"""

import pytest
from pydantic import ValidationError

from careroute.schema import Category, ClassificationResult, RiskFlags, UrgencyLevel


def _valid_kwargs():
    return dict(
        category=Category.HARDSHIP,
        risk_flags=RiskFlags(hardship=True, vulnerability=False, scam=False),
        urgency=UrgencyLevel.HIGH,
        confidence=0.87,
    )


def test_classification_result_accepts_valid_data():
    result = ClassificationResult(**_valid_kwargs())

    assert result.category == Category.HARDSHIP
    assert result.risk_flags == RiskFlags(hardship=True, vulnerability=False, scam=False)
    assert result.urgency == UrgencyLevel.HIGH
    assert result.confidence == 0.87


def test_category_has_exactly_seven_members():
    assert len(Category) == 7
    assert {member.value for member in Category} == {
        "complaint",
        "hardship",
        "vulnerability",
        "scam",
        "routine_query",
        "account_admin",
        "other",
    }


def test_risk_flags_has_exactly_three_boolean_fields():
    assert set(RiskFlags.model_fields.keys()) == {"hardship", "vulnerability", "scam"}
    for field_name, field_info in RiskFlags.model_fields.items():
        assert field_info.annotation is bool, f"{field_name} must be a bool field"


def test_schema_has_no_free_text_pii_surface():
    # Guards against a future edit sneaking a raw-message/free-text field
    # into the schema, which would create a PII leakage surface by
    # construction. The classifier output must stay limited to the four
    # structured fields.
    assert set(ClassificationResult.model_fields.keys()) == {
        "category",
        "risk_flags",
        "urgency",
        "confidence",
    }


@pytest.mark.parametrize("missing_field", ["category", "risk_flags", "urgency", "confidence"])
def test_rejects_missing_required_field(missing_field):
    kwargs = _valid_kwargs()
    del kwargs[missing_field]

    with pytest.raises(ValidationError):
        ClassificationResult(**kwargs)


def test_rejects_non_boolean_risk_flag_value():
    with pytest.raises(ValidationError):
        RiskFlags(hardship="not_a_bool", vulnerability=False, scam=False)


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, -5.0, 2.0])
def test_rejects_confidence_out_of_range(bad_confidence):
    kwargs = _valid_kwargs()
    kwargs["confidence"] = bad_confidence

    with pytest.raises(ValidationError):
        ClassificationResult(**kwargs)


def test_rejects_invalid_category_value():
    kwargs = _valid_kwargs()
    kwargs["category"] = "not_a_real_category"

    with pytest.raises(ValidationError):
        ClassificationResult(**kwargs)


def test_rejects_invalid_urgency_value():
    kwargs = _valid_kwargs()
    kwargs["urgency"] = "urgent!!"

    with pytest.raises(ValidationError):
        ClassificationResult(**kwargs)
