"""Integration tests for the LangGraph compliance pipeline.

Uses FakeChatModel that returns pre-built Pydantic objects.
"""

from __future__ import annotations

from typing import Any

import pytest

from mas.graph.builder import build_compliance_graph
from mas.rules.engine import RuleEngine
from mas.schemas.asset_flags import AssetFlag, AssetFlags
from mas.schemas.classification import MiCARClass
from mas.schemas.compliance_flags import ComplianceFlags, DisclosureFlag


def _f(value: bool) -> AssetFlag:
    return AssetFlag(value=value, evidence="test", confidence=0.9)


def _mock_asset_flags_emt() -> AssetFlags:
    """Flags that should classify as EMT."""
    return AssetFlags(
        regulated_as_security=_f(False),
        represents_equity=_f(False),
        represents_debt=_f(False),
        has_capital_rights=_f(False),
        investment_promise=_f(False),
        dividend_like=_f(False),
        security_language=_f(False),
        rights_transferable=_f(True),
        redeemable_in_fiat=_f(True),
        daily_redeemability=_f(True),
        reserve_assets_held=_f(True),
        audited_reserves=_f(True),
        redemption_policy_clear=_f(True),
        backed_by_assets=_f(False),
        utility_function=_f(False),
        governance_function=_f(False),
        nft_unique=_f(False),
        whitepaper_present=_f(True),
        disclaimers_regulatory=_f(True),
    )


def _mock_compliance_flags_emt() -> ComplianceFlags:
    return ComplianceFlags(
        micar_class="emt",
        disclosures=[
            DisclosureFlag(
                requirement_id=f"req_{i}",
                description=f"Disclosure {i}",
                fulfilled=i <= 9,
                evidence="p.5" if i <= 9 else "NOT FOUND",
                confidence=0.85,
            )
            for i in range(1, 13)
        ],
    )


class FakeStructuredOutput:
    def __init__(self, response: Any) -> None:
        self._response = response

    def invoke(self, messages: Any) -> Any:
        return self._response


class FakeChatModel:
    model_name: str = "fake-model"

    def __init__(self, responses: dict[type, Any]) -> None:
        self._responses = responses

    def with_structured_output(self, schema: type) -> FakeStructuredOutput:
        if schema not in self._responses:
            msg = f"No mock response for schema: {schema.__name__}"
            raise ValueError(msg)
        return FakeStructuredOutput(self._responses[schema])


@pytest.fixture
def fake_model() -> FakeChatModel:
    return FakeChatModel(
        responses={
            AssetFlags: _mock_asset_flags_emt(),
            ComplianceFlags: _mock_compliance_flags_emt(),
        }
    )


@pytest.fixture
def compiled_graph(fake_model: FakeChatModel, rule_engine: RuleEngine) -> Any:
    return build_compliance_graph(
        chat_model=fake_model,  # type: ignore[arg-type]
        rule_engine=rule_engine,
        prompt_version="v1",
    )


class TestFullPipeline:
    def test_emt_classification(self, compiled_graph: Any) -> None:
        result = compiled_graph.invoke({"whitepaper_text": "Test whitepaper."})

        assert result["asset_flags"].redeemable_in_fiat.value is True
        assert result["classification"].micar_class == MiCARClass.EMT
        assert "EMT_1" in result["classification"].triggered_rules
        assert len(result["compliance_flags"].disclosures) == 12
        assert result["input_hash"] != ""
        assert result["model_id"] == "fake-model"

    def test_pipeline_state_keys(self, compiled_graph: Any) -> None:
        result = compiled_graph.invoke({"whitepaper_text": "Test."})
        expected_keys = {
            "whitepaper_text",
            "input_hash",
            "asset_flags",
            "classification",
            "compliance_flags",
            "prompt_version",
            "model_id",
            "timestamp",
        }
        assert expected_keys.issubset(set(result.keys()))


class TestUtilityTokenPipeline:
    def test_utility_classification(self, rule_engine: RuleEngine) -> None:
        ut_flags = AssetFlags(
            **{name: _f(False) for name in AssetFlags.model_fields},
        )
        # Override specific flags for utility token
        ut_flags.utility_function = _f(True)
        ut_flags.whitepaper_present = _f(True)
        ut_flags.governance_function = _f(True)

        ut_compliance = ComplianceFlags(
            micar_class="other",
            disclosures=[
                DisclosureFlag(
                    requirement_id=f"req_{i}",
                    description=f"Disclosure {i}",
                    fulfilled=True,
                    evidence="p.10",
                    confidence=0.9,
                )
                for i in range(1, 7)
            ],
        )

        model = FakeChatModel(responses={AssetFlags: ut_flags, ComplianceFlags: ut_compliance})
        graph = build_compliance_graph(
            chat_model=model,  # type: ignore[arg-type]
            rule_engine=rule_engine,
            prompt_version="v1",
        )
        result = graph.invoke({"whitepaper_text": "Utility token whitepaper."})

        assert result["classification"].micar_class == MiCARClass.OTHER
        assert len(result["compliance_flags"].disclosures) == 6
