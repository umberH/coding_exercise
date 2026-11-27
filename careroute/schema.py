"""Shared classification schema for CareRoute.

This is the stable contract between every classification provider (rules now,
LLM later) and everything downstream (policy, API, UI, eval gate). Output is
limited to these four structured fields on purpose - adding a free-text field
here would reopen the PII leakage surface the redaction step closes.
"""

from enum import Enum

from pydantic import BaseModel, Field


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
    confidence: float = Field(ge=0.0, le=1.0)
