"""Tests for trust analysis schema, scoring, and pipeline integration."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mas.graph.builder import build_compliance_graph
from mas.rules.engine import RuleEngine
from mas.schemas.asset_flags import AssetFlag, AssetFlags
from mas.schemas.compliance_flags import ComplianceFlags, DisclosureFlag
from mas.schemas.trust_analysis import (
    RiskLevel,
    TrustAnalysisResult,
    TrustSignal,
    TrustSignals,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signal(score: int = 3) -> TrustSignal:
    """Create a TrustSignal with defaults."""
    return TrustSignal(score=score, evidence="test evidence", confidence=0.85)


def _make_signals(**overrides: int) -> TrustSignals:
    """Create TrustSignals with all scores defaulting to 3."""
    defaults = {name: 3 for name in TrustSignals.model_fields}
    defaults.update(overrides)
    return TrustSignals(**{k: _signal(v) for k, v in defaults.items()})


def _f(value: bool) -> AssetFlag:
    return AssetFlag(value=value, evidence="test", confidence=0.9)


# ---------------------------------------------------------------------------
# TrustSignal validation
# ---------------------------------------------------------------------------


class TestTrustSignal:
    def test_valid_signal(self) -> None:
        s = TrustSignal(score=4, evidence="See p.5", confidence=0.9)
        assert s.score == 4
        assert s.confidence == 0.9

    def test_score_too_low(self) -> None:
        with pytest.raises(ValidationError):
            TrustSignal(score=0, evidence="x", confidence=0.5)

    def test_score_too_high(self) -> None:
        with pytest.raises(ValidationError):
            TrustSignal(score=6, evidence="x", confidence=0.5)

    def test_score_edge_min(self) -> None:
        s = TrustSignal(score=1, evidence="x", confidence=0.0)
        assert s.score == 1

    def test_score_edge_max(self) -> None:
        s = TrustSignal(score=5, evidence="x", confidence=1.0)
        assert s.score == 5

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TrustSignal(score=3, evidence="x", confidence=1.5)
        with pytest.raises(ValidationError):
            TrustSignal(score=3, evidence="x", confidence=-0.1)


# ---------------------------------------------------------------------------
# TrustSignals model
# ---------------------------------------------------------------------------


class TestTrustSignals:
    def test_all_fields_present(self) -> None:
        assert len(TrustSignals.model_fields) == 8

    def test_json_round_trip(self) -> None:
        signals = _make_signals()
        json_str = signals.model_dump_json()
        restored = TrustSignals.model_validate_json(json_str)
        assert restored.team_transparency.score == signals.team_transparency.score


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestTrustScoring:
    def test_all_fives_gives_100(self) -> None:
        signals = _make_signals(
            team_transparency=5,
            tokenomics_clarity=5,
            audit_status=5,
            roadmap_realism=5,
            red_flags_detected=5,
            technical_depth=5,
            funding_transparency=5,
            community_governance=5,
        )
        score = TrustAnalysisResult.compute_score(signals)
        assert score == 100.0

    def test_all_ones_gives_20(self) -> None:
        signals = _make_signals(
            team_transparency=1,
            tokenomics_clarity=1,
            audit_status=1,
            roadmap_realism=1,
            red_flags_detected=1,
            technical_depth=1,
            funding_transparency=1,
            community_governance=1,
        )
        score = TrustAnalysisResult.compute_score(signals)
        assert score == 20.0

    def test_all_threes_gives_60(self) -> None:
        signals = _make_signals()
        score = TrustAnalysisResult.compute_score(signals)
        assert score == 60.0  # 3/5 = 60%

    def test_score_range(self) -> None:
        for s in range(1, 6):
            signals = _make_signals(**{name: s for name in TrustSignals.model_fields})
            score = TrustAnalysisResult.compute_score(signals)
            assert 0.0 <= score <= 100.0

    def test_weighted_calculation(self) -> None:
        """Verify weighted average with a known calculation."""
        signals = _make_signals(
            team_transparency=5,   # w=1.5 → 7.5
            red_flags_detected=1,  # w=2.0 → 2.0
            community_governance=5,  # w=0.5 → 2.5
            # rest at 3: tokenomics(1.5*3=4.5), audit(1.5*3=4.5),
            # roadmap(1.0*3=3.0), tech(1.0*3=3.0), funding(1.0*3=3.0)
        )
        score = TrustAnalysisResult.compute_score(signals)
        # manual: 7.5 + 4.5 + 4.5 + 3.0 + 2.0 + 3.0 + 3.0 + 2.5 = 30.0
        # max:    7.5 + 7.5 + 7.5 + 5.0 + 10.0 + 5.0 + 5.0 + 2.5 = 50.0
        expected = round(30.0 / 50.0 * 100, 2)
        assert score == expected


# ---------------------------------------------------------------------------
# Risk level classification
# ---------------------------------------------------------------------------


class TestRiskLevel:
    def test_low_risk_at_75(self) -> None:
        assert TrustAnalysisResult.classify_risk(75.0) == RiskLevel.LOW_RISK

    def test_low_risk_at_100(self) -> None:
        assert TrustAnalysisResult.classify_risk(100.0) == RiskLevel.LOW_RISK

    def test_moderate_at_55(self) -> None:
        assert TrustAnalysisResult.classify_risk(55.0) == RiskLevel.MODERATE

    def test_moderate_at_74(self) -> None:
        assert TrustAnalysisResult.classify_risk(74.9) == RiskLevel.MODERATE

    def test_elevated_at_35(self) -> None:
        assert TrustAnalysisResult.classify_risk(35.0) == RiskLevel.ELEVATED

    def test_elevated_at_54(self) -> None:
        assert TrustAnalysisResult.classify_risk(54.9) == RiskLevel.ELEVATED

    def test_high_risk_below_35(self) -> None:
        assert TrustAnalysisResult.classify_risk(34.9) == RiskLevel.HIGH_RISK

    def test_high_risk_at_20(self) -> None:
        assert TrustAnalysisResult.classify_risk(20.0) == RiskLevel.HIGH_RISK


# ---------------------------------------------------------------------------
# TrustAnalysisResult model
# ---------------------------------------------------------------------------


class TestTrustAnalysisResult:
    def test_disclaimer_present(self) -> None:
        signals = _make_signals()
        result = TrustAnalysisResult(
            signals=signals,
            overall_score=60.0,
            risk_level=RiskLevel.MODERATE,
        )
        assert "NOT" in result.disclaimer
        assert "investment" in result.disclaimer

    def test_json_includes_all_fields(self) -> None:
        signals = _make_signals()
        result = TrustAnalysisResult(
            signals=signals,
            overall_score=60.0,
            risk_level=RiskLevel.MODERATE,
        )
        data = result.model_dump()
        assert "signals" in data
        assert "overall_score" in data
        assert "risk_level" in data
        assert "disclaimer" in data


# ---------------------------------------------------------------------------
# Pipeline integration (parallel branch)
# ---------------------------------------------------------------------------


class _FakeStructuredOutput:
    def __init__(self, response: Any) -> None:
        self._response = response

    def invoke(self, messages: Any) -> Any:
        return self._response


class _FakeChatModel:
    model_name: str = "fake-trust-model"

    def __init__(self, responses: dict[type, Any]) -> None:
        self._responses = responses

    def with_structured_output(self, schema: type) -> _FakeStructuredOutput:
        if schema not in self._responses:
            msg = f"No mock for {schema.__name__}"
            raise ValueError(msg)
        return _FakeStructuredOutput(self._responses[schema])


def _mock_emt_asset_flags() -> AssetFlags:
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


def _mock_emt_compliance() -> ComplianceFlags:
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


class TestTrustPipeline:
    @pytest.fixture
    def trust_graph(self, rule_engine: RuleEngine) -> Any:
        model = _FakeChatModel(
            responses={
                AssetFlags: _mock_emt_asset_flags(),
                ComplianceFlags: _mock_emt_compliance(),
                TrustSignals: _make_signals(
                    team_transparency=4,
                    red_flags_detected=5,
                    audit_status=4,
                ),
            }
        )
        return build_compliance_graph(
            chat_model=model,  # type: ignore[arg-type]
            rule_engine=rule_engine,
            prompt_version="v1",
            enable_trust=True,
        )

    def test_parallel_branches_both_complete(self, trust_graph: Any) -> None:
        result = trust_graph.invoke({"whitepaper_text": "Test whitepaper."})
        assert "compliance_flags" in result
        assert "trust_analysis" in result

    def test_trust_result_structure(self, trust_graph: Any) -> None:
        result = trust_graph.invoke({"whitepaper_text": "Test whitepaper."})
        trust: TrustAnalysisResult = result["trust_analysis"]
        assert trust.signals.team_transparency.score == 4
        assert trust.signals.red_flags_detected.score == 5
        assert 0.0 <= trust.overall_score <= 100.0
        assert isinstance(trust.risk_level, RiskLevel)

    def test_compliance_branch_still_works(self, trust_graph: Any) -> None:
        result = trust_graph.invoke({"whitepaper_text": "Test."})
        assert result["classification"].micar_class.value == "emt"
        assert len(result["compliance_flags"].disclosures) == 12

    def test_pipeline_without_trust(self, rule_engine: RuleEngine) -> None:
        """Graph built without trust -> no trust_analysis in result."""
        model = _FakeChatModel(
            responses={
                AssetFlags: _mock_emt_asset_flags(),
                ComplianceFlags: _mock_emt_compliance(),
            }
        )
        graph = build_compliance_graph(
            chat_model=model,  # type: ignore[arg-type]
            rule_engine=rule_engine,
            prompt_version="v1",
            enable_trust=False,
        )
        result = graph.invoke({"whitepaper_text": "Test."})
        assert "trust_analysis" not in result
        assert "compliance_flags" in result

    def test_multiple_sequential_runs(self, trust_graph: Any) -> None:
        """Pipeline can be invoked multiple times without crashing."""
        r1 = trust_graph.invoke({"whitepaper_text": "First run."})
        r2 = trust_graph.invoke({"whitepaper_text": "Second run."})
        assert "trust_analysis" in r1
        assert "trust_analysis" in r2
        assert r1["trust_analysis"].overall_score == r2["trust_analysis"].overall_score

    def test_trust_with_contract_security(self, rule_engine: RuleEngine) -> None:
        """GoPlus modifier is applied when contract_security is in state."""
        from mas.agents.goplus import ContractSecurity

        model = _FakeChatModel(
            responses={
                AssetFlags: _mock_emt_asset_flags(),
                ComplianceFlags: _mock_emt_compliance(),
                TrustSignals: _make_signals(),  # all 3s → base score 60%
            }
        )
        graph = build_compliance_graph(
            chat_model=model,  # type: ignore[arg-type]
            rule_engine=rule_engine,
            prompt_version="v1",
            enable_trust=True,
        )

        # Without contract_security
        r_without = graph.invoke({"whitepaper_text": "Test."})
        score_without = r_without["trust_analysis"].overall_score

        # With contract_security (honeypot → -30 modifier)
        honeypot = ContractSecurity(
            chain="ethereum",
            address="0xbad",
            is_honeypot=True,
        )
        r_with = graph.invoke({
            "whitepaper_text": "Test.",
            "contract_security": honeypot,
        })
        score_with = r_with["trust_analysis"].overall_score

        assert score_with < score_without
        assert r_with["trust_analysis"].contract_modifier == -30.0
