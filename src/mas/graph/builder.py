"""Build and compile the LangGraph compliance analysis pipeline.

Supports two modes:
- **Direct analysis**: provide ``whitepaper_text`` → 3-node pipeline
- **Search + analyze**: provide ``project_query`` → 5-node pipeline
  (Searcher → Crawler → extract_flags → classify → verify_disclosure)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from mas.agents.crawler import WebCrawler, make_crawler_node
from mas.agents.searcher import CoinGeckoSearcher, make_searcher_node
from mas.graph.nodes import make_classify_node, make_disclosure_node, make_extract_node
from mas.schemas.state import ComplianceState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.graph.state import CompiledStateGraph

    from mas.rules.engine import RuleEngine


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


def build_compliance_graph(
    chat_model: BaseChatModel,
    rule_engine: RuleEngine,
    prompt_version: str = "v1",
    searcher: CoinGeckoSearcher | None = None,
    crawler: WebCrawler | None = None,
) -> CompiledStateGraph:
    """Build and compile the compliance analysis StateGraph.

    The graph supports conditional routing:

    - If invoked with ``{"whitepaper_text": "..."}`` → direct 3-node analysis
    - If invoked with ``{"project_query": "tether"}`` → 5-node pipeline
      with Searcher and Crawler prepended

    Args:
        chat_model: A LangChain chat model instance.
        rule_engine: The YAML-driven rule engine for classification.
        prompt_version: Prompt version directory to use.
        searcher: CoinGecko searcher instance (required for search mode).
        crawler: Web crawler instance (required for search mode).

    Returns:
        A compiled StateGraph ready for invocation.
    """
    graph: StateGraph[Any] = StateGraph(ComplianceState)

    # Data acquisition nodes (optional)
    if searcher and crawler:
        graph.add_node("searcher", make_searcher_node(searcher))
        graph.add_node("crawler", make_crawler_node(crawler))

    # Analysis nodes
    graph.add_node("extract_flags", make_extract_node(chat_model, prompt_version))
    graph.add_node("classify", make_classify_node(rule_engine))
    graph.add_node(
        "verify_disclosure",
        make_disclosure_node(chat_model, rule_engine, prompt_version),
    )

    # Conditional routing from START
    if searcher and crawler:
        graph.add_conditional_edges(
            START,
            _route_input,
            {"search": "searcher", "analyze": "extract_flags"},
        )
        graph.add_edge("searcher", "crawler")
        graph.add_edge("crawler", "extract_flags")
    else:
        graph.add_edge(START, "extract_flags")

    # Analysis edges (always present)
    graph.add_edge("extract_flags", "classify")
    graph.add_edge("classify", "verify_disclosure")
    graph.add_edge("verify_disclosure", END)

    return graph.compile()
