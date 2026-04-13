"""Factory functions to build the pipeline from configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mas.config import Settings
from mas.graph.builder import build_compliance_graph
from mas.rules.engine import RuleEngine

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


def create_pipeline(settings: Settings | None = None) -> CompiledStateGraph:
    """Build a compiled compliance pipeline from settings.

    In mock mode, uses FakeChatModel with pre-computed fixtures.
    Otherwise, uses ChatOpenAI with structured output.
    """
    if settings is None:
        settings = Settings()

    rule_engine = RuleEngine(rules_dir=settings.rules_dir)

    if settings.mock_mode:
        chat_model = _create_mock_model(settings.fixtures_dir)
    else:
        chat_model = _create_openai_model(settings)

    return build_compliance_graph(
        chat_model=chat_model,
        rule_engine=rule_engine,
        prompt_version=settings.prompt_version,
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

    # Look for fixture files
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
        msg = f"No mock fixtures found in {fixtures_dir}. Create fixture files first."
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
