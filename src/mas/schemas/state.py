"""LangGraph shared state for the compliance analysis pipeline."""

from __future__ import annotations

from typing import TypedDict

from mas.agents.goplus import ContractSecurity
from mas.schemas.asset_flags import AssetFlags
from mas.schemas.classification import ClassificationResult
from mas.schemas.compliance_flags import ComplianceFlags
from mas.schemas.project import ProjectMetadata
from mas.schemas.trust_analysis import TrustAnalysisResult


class ComplianceState(TypedDict, total=False):
    """Shared state flowing through the LangGraph StateGraph.

    Each node reads from and writes to this state. Using ``total=False``
    allows nodes to populate fields incrementally.
    """

    # Data acquisition input (Searcher + Crawler)
    project_query: str  # e.g. "tether", "uniswap", "USDT"
    project_metadata: ProjectMetadata
    crawled_urls: list[str]

    # Analysis input
    whitepaper_text: str
    input_hash: str

    # Stage 1 output
    asset_flags: AssetFlags

    # Stage 2 output
    classification: ClassificationResult

    # Stage 3 output
    compliance_flags: ComplianceFlags

    # Trust analysis output (parallel branch)
    trust_analysis: TrustAnalysisResult

    # On-chain contract security (GoPlus)
    contract_security: ContractSecurity

    # Metadata
    prompt_version: str
    model_id: str
    timestamp: str
