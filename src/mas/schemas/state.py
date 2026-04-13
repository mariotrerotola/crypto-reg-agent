"""LangGraph shared state for the compliance analysis pipeline."""

from __future__ import annotations

from typing import TypedDict

from mas.schemas.asset_flags import AssetFlags
from mas.schemas.classification import ClassificationResult
from mas.schemas.compliance_flags import ComplianceFlags


class ComplianceState(TypedDict, total=False):
    """Shared state flowing through the LangGraph StateGraph.

    Each node reads from and writes to this state. Using ``total=False``
    allows nodes to populate fields incrementally.
    """

    # Input
    whitepaper_text: str
    input_hash: str

    # Stage 1 output
    asset_flags: AssetFlags

    # Stage 2 output
    classification: ClassificationResult

    # Stage 3 output
    compliance_flags: ComplianceFlags

    # Metadata
    prompt_version: str
    model_id: str
    timestamp: str
