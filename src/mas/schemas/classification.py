"""Stage 2 output: deterministic classification from the rule engine.

The ``MiCARClass`` enum covers EU MiCAR categories from Section 4.3 of
the paper.  Other jurisdictions use plain string values — see
``ClassificationResult.asset_class`` for the generic accessor.
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
    """Output of the deterministic rule engine (Stage 2).

    For MiCAR, ``micar_class`` is a ``MiCARClass`` enum value.
    For other jurisdictions (e.g. SEC), it holds a plain string
    cast to ``MiCARClass`` via the fallback ``_missing_`` handler,
    and the original string is preserved in ``jurisdiction_class``.
    """

    micar_class: MiCARClass
    triggered_rules: list[str] = Field(
        description="IDs of the rules that matched in the classification."
    )
    explanation: str = Field(description="Human-readable reasoning chain for the classification.")
    jurisdiction: str = Field(
        default="EU-MiCAR",
        description="Jurisdiction identifier (e.g. 'EU-MiCAR', 'US-SEC').",
    )
    jurisdiction_class: str = Field(
        default="",
        description=(
            "Original class label from the jurisdiction rules "
            "(e.g. 'investment_contract')."
        ),
    )
