"""Build and compile the LangGraph compliance analysis pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from mas.graph.nodes import make_classify_node, make_disclosure_node, make_extract_node
from mas.schemas.state import ComplianceState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.graph.state import CompiledStateGraph

    from mas.rules.engine import RuleEngine


def build_compliance_graph(
    chat_model: BaseChatModel,
    rule_engine: RuleEngine,
    prompt_version: str = "v1",
) -> CompiledStateGraph:
    """Build and compile the 3-stage compliance analysis StateGraph.

    Nodes:
        1. ``extract_flags`` — LLM extracts AssetFlags from whitepaper
        2. ``classify`` — Rule engine classifies MiCAR class (no LLM)
        3. ``verify_disclosure`` — LLM verifies disclosure requirements

    Args:
        chat_model: A LangChain chat model instance (e.g. ``ChatOpenAI``).
        rule_engine: The YAML-driven rule engine for classification.
        prompt_version: Prompt version directory to use.

    Returns:
        A compiled StateGraph ready for invocation.
    """
    graph = StateGraph(ComplianceState)

    graph.add_node("extract_flags", make_extract_node(chat_model, prompt_version))
    graph.add_node("classify", make_classify_node(rule_engine))
    graph.add_node(
        "verify_disclosure",
        make_disclosure_node(chat_model, rule_engine, prompt_version),
    )

    graph.add_edge(START, "extract_flags")
    graph.add_edge("extract_flags", "classify")
    graph.add_edge("classify", "verify_disclosure")
    graph.add_edge("verify_disclosure", END)

    return graph.compile()
