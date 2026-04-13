"""Stage 2 output: deterministic MiCAR classification from the rule engine.

Categories from Section 4.3 of the paper: SECURITY, EMT, ART, OTHER,
NON_MICAR, NON_CLASSIFIABLE.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class MiCARClass(StrEnum):
    """MiCAR crypto-asset taxonomic categories (Section 4.3 of the paper)."""

    SECURITY = "security"
    EMT = "emt"  # E-Money Token — Title IV
    ART = "art"  # Asset-Referenced Token — Title III
    OTHER = "other"  # Utility / Governance token
    NON_MICAR = "non_micar"  # Outside MiCAR scope
    NON_CLASSIFIABLE = "non_classifiable"  # No crypto indicators detected


class ClassificationResult(BaseModel):
    """Output of the deterministic rule engine (Stage 2)."""

    micar_class: MiCARClass
    triggered_rules: list[str] = Field(
        description="IDs of the rules that matched in the classification."
    )
    explanation: str = Field(description="Human-readable reasoning chain for the classification.")
