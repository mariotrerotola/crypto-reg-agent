"""Factory functions to build the pipeline from configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mas.agents.crawler import WebCrawler
from mas.agents.searcher import CoinGeckoSearcher
from mas.config import Settings
from mas.graph.builder import build_compliance_graph
from mas.rules.engine import RuleEngine

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


def create_pipeline(
    settings: Settings | None = None,
    enable_search: bool = True,
) -> CompiledStateGraph:
    """Build a compiled compliance pipeline from settings.

    Args:
        settings: Application settings. Defaults to loading from env.
        enable_search: If True, include Searcher + Crawler nodes for
            project discovery. If False, only the 3-node analysis pipeline.
    """
    if settings is None:
        settings = Settings()

    rule_engine = RuleEngine(rules_dir=settings.rules_dir)

    if settings.mock_mode:
        chat_model = _create_mock_model(settings.fixtures_dir)
        searcher = None
        crawler = None
    else:
        chat_model = _create_openai_model(settings)
        if enable_search:
            searcher = CoinGeckoSearcher(
                api_key=settings.coingecko_api_key or None,
                timeout=settings.crawler_timeout,
            )
            crawler = WebCrawler(
                timeout=settings.crawler_timeout,
                max_urls=settings.crawler_max_urls,
            )
        else:
            searcher = None
            crawler = None

    return build_compliance_graph(
        chat_model=chat_model,
        rule_engine=rule_engine,
        prompt_version=settings.prompt_version,
        searcher=searcher,
        crawler=crawler,
    )


def _create_openai_model(settings: Settings) -> Any:
    """Create a ChatOpenAI instance."""
    from langchain_openai import ChatOpenAI

    if not settings.openai_api_key:
        msg = (
            "OPENAI_API_KEY not set. Either set MAS_OPENAI_API_KEY in your "
            "environment or .env file, or use MAS_MOCK_MODE=true for demo mode."
        )
        raise ValueError(msg)

    return ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.temperature,
        seed=settings.seed,
        api_key=settings.openai_api_key,
    )


def _create_mock_model(fixtures_dir: Path) -> Any:
    """Create a FakeChatModel using pre-computed fixture files."""
    from mas.schemas.asset_flags import AssetFlags
    from mas.schemas.compliance_flags import ComplianceFlags

    responses: dict[type, Any] = {}

    for example_dir in sorted(fixtures_dir.iterdir()) if fixtures_dir.exists() else []:
        if not example_dir.is_dir():
            continue
        stage1 = example_dir / "stage1_asset_flags.json"
        stage3 = example_dir / "stage3_compliance_flags.json"

        if stage1.exists() and AssetFlags not in responses:
            data = json.loads(stage1.read_text())
            responses[AssetFlags] = AssetFlags.model_validate(data)

        if stage3.exists() and ComplianceFlags not in responses:
            data = json.loads(stage3.read_text())
            responses[ComplianceFlags] = ComplianceFlags.model_validate(data)

    if not responses:
        msg = f"No mock fixtures found in {fixtures_dir}."
        raise FileNotFoundError(msg)

    return _FakeChatModel(responses)


class _FakeStructuredOutput:
    def __init__(self, response: Any) -> None:
        self._response = response

    def invoke(self, messages: Any) -> Any:
        return self._response


class _FakeChatModel:
    """Minimal fake chat model for mock mode."""

    model_name: str = "mock-v1"

    def __init__(self, responses: dict[type, Any]) -> None:
        self._responses = responses

    def with_structured_output(self, schema: type) -> _FakeStructuredOutput:
        if schema not in self._responses:
            msg = f"No mock fixture for {schema.__name__}"
            raise ValueError(msg)
        return _FakeStructuredOutput(self._responses[schema])
