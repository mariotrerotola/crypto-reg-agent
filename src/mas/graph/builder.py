"""Build and compile the LangGraph compliance analysis pipeline.

Supports two modes:
- **Direct analysis**: provide ``whitepaper_text`` → 3-node pipeline
- **Search + analyze**: provide ``project_query`` → 5-node pipeline
  (Searcher → Crawler → extract_flags → classify → verify_disclosure)

When ``enable_trust=True``, a parallel trust analysis branch is added:
both the compliance branch and the trust analysis branch run concurrently
on the same whitepaper text, and LangGraph auto-merges the results.

When a ``goplus`` client is provided (search mode), an on-chain security
check node runs after the crawler and before the analysis branches,
injecting ``contract_security`` into the state for the trust scorer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from mas.agents.crawler import WebCrawler, make_crawler_node
from mas.agents.goplus import GoPlusClient
from mas.agents.searcher import CoinGeckoSearcher, make_searcher_node
from mas.graph.nodes import (
    make_classify_node,
    make_disclosure_node,
    make_extract_node,
    make_trust_node,
)
from mas.schemas.project import ProjectMetadata
from mas.schemas.state import ComplianceState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.graph.state import CompiledStateGraph

    from mas.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


def _route_input(state: ComplianceState) -> str:
    """Conditional router: decide whether to search or analyze directly.

    If ``whitepaper_text`` is already present → go straight to analysis.
    If ``project_query`` is provided → run Searcher + Crawler first.
    """
    if state.get("whitepaper_text"):
        return "analyze"
    if state.get("project_query"):
        return "search"
    msg = "State must contain either 'whitepaper_text' or 'project_query'"
    raise ValueError(msg)


def _passthrough(state: ComplianceState) -> dict[str, Any]:
    """No-op node used as a fork point for parallel branches."""
    return {}


def _fork_to_branches(state: ComplianceState) -> list[str]:
    """Fan out to compliance and trust analysis branches in parallel."""
    return ["extract_flags", "trust_analysis"]


def _make_goplus_node(goplus: GoPlusClient) -> Any:
    """Create a GoPlus security check node.

    Reads contract addresses from ``project_metadata`` and runs the first
    available address through GoPlus, writing ``contract_security`` to state.
    """

    def goplus_check(state: ComplianceState) -> dict[str, Any]:
        metadata: ProjectMetadata | None = state.get("project_metadata")  # type: ignore[assignment]
        if not metadata or not metadata.contract_addresses:
            return {}

        # Check the first available contract
        for chain, address in metadata.contract_addresses.items():
            logger.info("GoPlus: checking %s on %s", address[:16], chain)
            result = goplus.check_token(chain, address)
            if result:
                flags = result.red_flag_count
                warns = result.warning_count
                mod = result.trust_modifier()
                logger.info(
                    "GoPlus: %d red flags, %d warnings, modifier %+.0f",
                    flags, warns, mod,
                )
                return {"contract_security": result}
        return {}

    return goplus_check


def build_compliance_graph(
    chat_model: BaseChatModel,
    rule_engine: RuleEngine,
    prompt_version: str = "v1",
    searcher: CoinGeckoSearcher | None = None,
    crawler: WebCrawler | None = None,
    goplus: GoPlusClient | None = None,
    enable_trust: bool = False,
) -> CompiledStateGraph:
    """Build and compile the compliance analysis StateGraph.

    The graph supports conditional routing:

    - If invoked with ``{"whitepaper_text": "..."}`` → direct analysis
    - If invoked with ``{"project_query": "tether"}`` → search pipeline
      with Searcher and Crawler prepended

    When ``enable_trust=True``, a parallel trust analysis branch runs
    alongside the compliance analysis. Both branches read from the same
    ``whitepaper_text`` and write to separate state keys, which LangGraph
    merges automatically.

    Args:
        chat_model: A LangChain chat model instance.
        rule_engine: The YAML-driven rule engine for classification.
        prompt_version: Prompt version directory to use.
        searcher: CoinGecko searcher instance (required for search mode).
        crawler: Web crawler instance (required for search mode).
        goplus: GoPlus Security client for on-chain checks (optional).
        enable_trust: If True, add a parallel trust analysis branch.

    Returns:
        A compiled StateGraph ready for invocation.
    """
    graph: StateGraph[Any] = StateGraph(ComplianceState)

    # Data acquisition nodes (optional)
    if searcher and crawler:
        graph.add_node("searcher", make_searcher_node(searcher))
        graph.add_node("crawler", make_crawler_node(crawler))

    # GoPlus security check (only in search mode with contract addresses)
    has_goplus = goplus is not None and searcher is not None
    if has_goplus:
        graph.add_node("goplus_check", _make_goplus_node(goplus))  # type: ignore[arg-type]

    # Analysis nodes
    graph.add_node("extract_flags", make_extract_node(chat_model, prompt_version))
    graph.add_node("classify", make_classify_node(rule_engine))
    graph.add_node(
        "verify_disclosure",
        make_disclosure_node(chat_model, rule_engine, prompt_version),
    )

    # Trust analysis parallel branch
    if enable_trust:
        graph.add_node("fork", _passthrough)
        graph.add_node(
            "trust_analysis",
            make_trust_node(chat_model, prompt_version),
        )

    # Determine the target after data acquisition
    analyze_target = "fork" if enable_trust else "extract_flags"

    # Conditional routing from START
    if searcher and crawler:
        graph.add_conditional_edges(
            START,
            _route_input,
            {"search": "searcher", "analyze": analyze_target},
        )
        graph.add_edge("searcher", "crawler")
        if has_goplus:
            graph.add_edge("crawler", "goplus_check")
            graph.add_edge("goplus_check", analyze_target)
        else:
            graph.add_edge("crawler", analyze_target)
    else:
        graph.add_edge(START, analyze_target)

    # Fan-out from fork to parallel branches
    if enable_trust:
        graph.add_conditional_edges("fork", _fork_to_branches)

    # Compliance branch edges (sequential)
    graph.add_edge("extract_flags", "classify")
    graph.add_edge("classify", "verify_disclosure")
    graph.add_edge("verify_disclosure", END)

    # Trust branch terminates at END independently
    if enable_trust:
        graph.add_edge("trust_analysis", END)

    return graph.compile()
