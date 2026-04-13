"""Stage 3 output: disclosure verification results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DisclosureFlag(BaseModel):
    """A single disclosure requirement check."""

    requirement_id: str = Field(description="ID from the disclosure checklist, e.g. 'ART_D1'.")
    description: str = Field(description="What the whitepaper must disclose.")
    fulfilled: bool = Field(description="Whether the disclosure requirement is met.")
    evidence: str = Field(
        description="Quote or page reference supporting this assessment, or 'NOT FOUND'."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM self-reported confidence in this assessment.",
    )


class ComplianceFlags(BaseModel):
    """Aggregate disclosure verification results for a given MiCAR class."""

    micar_class: str = Field(description="Echoed MiCAR class for traceability.")
    disclosures: list[DisclosureFlag] = Field(description="List of disclosure requirement checks.")
