"""Tests for Pydantic schema validation and computed fields."""

from datetime import UTC, datetime

import pytest

from mas.schemas import (
    AssetFlag,
    AssetFlags,
    ClassificationResult,
    ComplianceFlags,
    ComplianceReport,
    DisclosureFlag,
    MiCARClass,
)


def _make_flag(value: bool = True) -> AssetFlag:
    return AssetFlag(value=value, evidence="test evidence", confidence=0.95)


def _make_asset_flags(**overrides: bool) -> AssetFlags:
    defaults = {
        "regulated_as_security": False,
        "represents_equity": False,
        "represents_debt": False,
        "has_capital_rights": False,
        "investment_promise": False,
        "dividend_like": False,
        "security_language": False,
        "rights_transferable": False,
        "redeemable_in_fiat": False,
        "daily_redeemability": False,
        "reserve_assets_held": False,
        "audited_reserves": False,
        "redemption_policy_clear": False,
        "backed_by_assets": False,
        "utility_function": False,
        "governance_function": False,
        "nft_unique": False,
        "whitepaper_present": True,
        "disclaimers_regulatory": False,
    }
    defaults.update(overrides)
    return AssetFlags(**{k: _make_flag(v) for k, v in defaults.items()})


class TestAssetFlag:
    def test_valid_flag(self) -> None:
        flag = AssetFlag(value=True, evidence="See page 3", confidence=0.9)
        assert flag.value is True
        assert flag.evidence == "See page 3"
        assert flag.confidence == 0.9

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValueError):
            AssetFlag(value=True, evidence="x", confidence=1.5)
        with pytest.raises(ValueError):
            AssetFlag(value=True, evidence="x", confidence=-0.1)

    def test_confidence_edge_values(self) -> None:
        AssetFlag(value=True, evidence="x", confidence=0.0)
        AssetFlag(value=True, evidence="x", confidence=1.0)


class TestAssetFlags:
    def test_to_bool_dict(self) -> None:
        flags = _make_asset_flags(
            regulated_as_security=True,
            redeemable_in_fiat=True,
        )
        d = flags.to_bool_dict()
        assert d["regulated_as_security"] is True
        assert d["redeemable_in_fiat"] is True
        assert d["backed_by_assets"] is False
        assert len(d) == 19

    def test_all_fields_present(self) -> None:
        assert len(AssetFlags.model_fields) == 19

    def test_json_round_trip(self) -> None:
        flags = _make_asset_flags(utility_function=True)
        json_str = flags.model_dump_json()
        restored = AssetFlags.model_validate_json(json_str)
        assert restored.utility_function.value is True
        assert restored.to_bool_dict() == flags.to_bool_dict()


class TestMiCARClass:
    def test_enum_values(self) -> None:
        assert MiCARClass.SECURITY == "security"
        assert MiCARClass.EMT == "emt"
        assert MiCARClass.ART == "art"
        assert MiCARClass.OTHER == "other"
        assert MiCARClass.NON_MICAR == "non_micar"
        assert MiCARClass.NON_CLASSIFIABLE == "non_classifiable"

    def test_all_six_categories(self) -> None:
        assert len(MiCARClass) == 6


class TestClassificationResult:
    def test_valid(self) -> None:
        result = ClassificationResult(
            micar_class=MiCARClass.EMT,
            triggered_rules=["EMT_1"],
            explanation="Redeemable in fiat, audited reserves",
        )
        assert result.micar_class == MiCARClass.EMT
        assert result.triggered_rules == ["EMT_1"]


class TestDisclosureFlag:
    def test_valid(self) -> None:
        flag = DisclosureFlag(
            requirement_id="whitepaper_present",
            description="Whitepaper must be present",
            fulfilled=True,
            evidence="See section 2.1",
            confidence=0.85,
        )
        assert flag.fulfilled is True
        assert flag.requirement_id == "whitepaper_present"


class TestComplianceFlags:
    def test_dynamic_list(self) -> None:
        flags = ComplianceFlags(
            micar_class="emt",
            disclosures=[
                DisclosureFlag(
                    requirement_id="whitepaper_present",
                    description="Whitepaper disclosure",
                    fulfilled=True,
                    evidence="p.5",
                    confidence=0.9,
                ),
                DisclosureFlag(
                    requirement_id="redeemable_in_fiat",
                    description="Fiat redemption",
                    fulfilled=False,
                    evidence="NOT FOUND",
                    confidence=0.8,
                ),
            ],
        )
        assert len(flags.disclosures) == 2


class TestComplianceReport:
    def _make_report(self, fulfilled: int, total: int) -> ComplianceReport:
        disclosures = [
            DisclosureFlag(
                requirement_id=f"D{i}",
                description=f"Disclosure {i}",
                fulfilled=i < fulfilled,
                evidence="evidence" if i < fulfilled else "NOT FOUND",
                confidence=0.9,
            )
            for i in range(total)
        ]
        return ComplianceReport(
            input_hash="abc123",
            timestamp=datetime.now(UTC),
            prompt_version="v1|test",
            model_id="gpt-4o",
            asset_flags=_make_asset_flags(),
            classification=ClassificationResult(
                micar_class=MiCARClass.OTHER,
                triggered_rules=["OTHER_1"],
                explanation="test",
            ),
            compliance_flags=ComplianceFlags(
                micar_class="other",
                disclosures=disclosures,
            ),
        )

    def test_compliance_score_all_fulfilled(self) -> None:
        report = self._make_report(fulfilled=5, total=5)
        assert report.compliance_score == 1.0

    def test_compliance_score_none_fulfilled(self) -> None:
        report = self._make_report(fulfilled=0, total=5)
        assert report.compliance_score == 0.0

    def test_compliance_score_partial(self) -> None:
        report = self._make_report(fulfilled=3, total=10)
        assert report.compliance_score == 0.3

    def test_compliance_score_empty(self) -> None:
        report = self._make_report(fulfilled=0, total=0)
        assert report.compliance_score == 0.0

    def test_fulfilled_count(self) -> None:
        report = self._make_report(fulfilled=3, total=5)
        assert report.fulfilled_count == 3

    def test_total_disclosures(self) -> None:
        report = self._make_report(fulfilled=3, total=5)
        assert report.total_disclosures == 5

    def test_json_includes_computed_fields(self) -> None:
        report = self._make_report(fulfilled=2, total=4)
        data = report.model_dump()
        assert "compliance_score" in data
        assert data["compliance_score"] == 0.5
