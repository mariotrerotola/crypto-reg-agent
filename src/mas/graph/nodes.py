"""LangGraph node functions for the 3-stage compliance pipeline.

Each node function takes a ComplianceState dict, performs its work,
and returns a partial state update dict.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mas.prompts.loader import load_prompt, prompt_version_tag
from mas.schemas.asset_flags import AssetFlags
from mas.schemas.classification import ClassificationResult
from mas.schemas.compliance_flags import ComplianceFlags
from mas.schemas.state import ComplianceState
from mas.schemas.trust_analysis import TrustAnalysisResult, TrustSignals

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from mas.rules.engine import RuleEngine


def make_extract_node(
    chat_model: BaseChatModel,
    prompt_version: str = "v1",
) -> Any:
    """Create the Stage 1 node: extract AssetFlags from whitepaper text.

    Uses LangChain's ``.with_structured_output()`` to bind the Pydantic
    model directly to the chat model.
    """
    system_prompt = load_prompt("asset_flags", prompt_version)
    structured_model = chat_model.with_structured_output(AssetFlags)

    def extract_flags(state: ComplianceState) -> dict[str, Any]:
        whitepaper_text = state["whitepaper_text"]
        input_hash = hashlib.sha256(whitepaper_text.encode()).hexdigest()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": whitepaper_text},
        ]
        asset_flags: AssetFlags = structured_model.invoke(messages)  # type: ignore[assignment]

        return {
            "asset_flags": asset_flags,
            "input_hash": input_hash,
            "prompt_version": prompt_version_tag(prompt_version),
            "model_id": getattr(chat_model, "model_name", "unknown"),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    return extract_flags


def make_classify_node(rule_engine: RuleEngine) -> Any:
    """Create the Stage 2 node: deterministic MiCAR classification.

    This node does NOT call an LLM. It uses the YAML-driven rule engine
    to classify the asset based on the extracted flags.
    """

    def classify(state: ComplianceState) -> dict[str, Any]:
        asset_flags: AssetFlags = state["asset_flags"]
        bool_flags = asset_flags.to_bool_dict()
        classification: ClassificationResult = rule_engine.classify(bool_flags)
        return {"classification": classification}

    return classify


def make_disclosure_node(
    chat_model: BaseChatModel,
    rule_engine: RuleEngine,
    prompt_version: str = "v1",
) -> Any:
    """Create the Stage 3 node: verify disclosure requirements.

    Loads the disclosure checklist for the classified MiCAR class,
    formats it into the system prompt, and asks the LLM to verify
    each requirement against the whitepaper text.
    """
    prompt_template = load_prompt("compliance", prompt_version)

    def verify_disclosure(state: ComplianceState) -> dict[str, Any]:
        classification: ClassificationResult = state["classification"]
        micar_class = classification.micar_class.value
        whitepaper_text = state["whitepaper_text"]

        checklist = rule_engine.get_disclosure_checklist(micar_class)
        checklist_text = "\n".join(
            f"- **{item['id']}**: {item['description']}" for item in checklist
        )

        system_prompt = prompt_template.replace("{micar_class}", micar_class).replace(
            "{disclosure_checklist}", checklist_text
        )

        structured_model = chat_model.with_structured_output(ComplianceFlags)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": whitepaper_text},
        ]
        compliance_flags: ComplianceFlags = structured_model.invoke(messages)  # type: ignore[assignment]

        return {"compliance_flags": compliance_flags}

    return verify_disclosure


def make_trust_node(
    chat_model: BaseChatModel,
    prompt_version: str = "v1",
) -> Any:
    """Create the trust analysis node: extract TrustSignals from whitepaper text.

    Runs in parallel with the compliance branch.  Uses structured output
    for signal extraction, then deterministic scoring and risk classification.
    """
    system_prompt = load_prompt("trust_analysis", prompt_version)
    structured_model = chat_model.with_structured_output(TrustSignals)

    def trust_analysis(state: ComplianceState) -> dict[str, Any]:
        whitepaper_text = state["whitepaper_text"]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": whitepaper_text},
        ]
        signals: TrustSignals = structured_model.invoke(messages)  # type: ignore[assignment]

        base_score = TrustAnalysisResult.compute_score(signals)

        # Apply on-chain security modifier if available
        contract_sec = state.get("contract_security")
        modifier = contract_sec.trust_modifier() if contract_sec else 0.0
        overall_score = max(0.0, min(100.0, round(base_score + modifier, 2)))

        risk_level = TrustAnalysisResult.classify_risk(overall_score)

        result = TrustAnalysisResult(
            signals=signals,
            overall_score=overall_score,
            contract_modifier=modifier,
            risk_level=risk_level,
        )
        return {"trust_analysis": result}

    return trust_analysis
