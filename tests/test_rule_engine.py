"""Exhaustive tests for the YAML-driven rule engine.

Coverage target: >70% of engine.py. Every rule in classification.yaml
must have at least one test that triggers it and one that does not.
"""

from pathlib import Path

import pytest

from mas.rules.engine import RuleEngine, RuleEngineError
from mas.schemas.classification import MiCARClass
from tests.conftest import make_flags

RULES_DIR = Path(__file__).parent.parent / "src" / "mas" / "rules" / "micar_v1"


# --- SECURITY classification tests ---


class TestSecurityClassification:
    """Tests for rules SEC_1 and SEC_2."""

    def test_regulated_as_security_with_investment_promise(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(regulated_as_security=True, investment_promise=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.SECURITY
        assert "SEC_1" in result.triggered_rules

    def test_represents_equity_with_investment_promise(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(represents_equity=True, investment_promise=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.SECURITY

    def test_represents_debt_with_investment_promise(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(represents_debt=True, investment_promise=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.SECURITY

    def test_capital_rights_dividend_security_language(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(has_capital_rights=True, dividend_like=True, security_language=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.SECURITY
        assert "SEC_2" in result.triggered_rules

    def test_security_language_alone_not_security(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(security_language=True)
        result = rule_engine.classify(flags)
        assert result.micar_class != MiCARClass.SECURITY


# --- EMT classification tests ---


class TestEMTClassification:
    """Tests for rules EMT_1 and EMT_2."""

    def test_classic_emt_redeemable_audited(self, rule_engine: RuleEngine) -> None:
        """USDT/USDC-like: redeemable in fiat, audited reserves."""
        flags = make_flags(redeemable_in_fiat=True, audited_reserves=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.EMT
        assert "EMT_1" in result.triggered_rules

    def test_emt_excluded_by_backed_by_assets(self, rule_engine: RuleEngine) -> None:
        """Redeemable but backed by asset basket -> not EMT (excluded by 'none')."""
        flags = make_flags(redeemable_in_fiat=True, audited_reserves=True, backed_by_assets=True)
        result = rule_engine.classify(flags)
        assert result.micar_class != MiCARClass.EMT

    def test_emt_excluded_by_utility_function(self, rule_engine: RuleEngine) -> None:
        """Redeemable but also a utility token -> not EMT_1."""
        flags = make_flags(redeemable_in_fiat=True, audited_reserves=True, utility_function=True)
        result = rule_engine.classify(flags)
        assert "EMT_1" not in result.triggered_rules

    def test_emt_via_reserve_and_redemption_policy(self, rule_engine: RuleEngine) -> None:
        """EMT_2: redeemable with reserve assets and clear policy."""
        flags = make_flags(
            redeemable_in_fiat=True,
            reserve_assets_held=True,
            redemption_policy_clear=True,
        )
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.EMT


# --- ART classification tests ---


class TestARTClassification:
    """Tests for rule ART_1."""

    def test_backed_by_assets(self, rule_engine: RuleEngine) -> None:
        """Classic ART: backed by basket of assets."""
        flags = make_flags(backed_by_assets=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.ART
        assert "ART_1" in result.triggered_rules

    def test_not_backed_not_art(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(backed_by_assets=False)
        result = rule_engine.classify(flags)
        assert result.micar_class != MiCARClass.ART


# --- OTHER classification tests ---


class TestOtherClassification:
    """Tests for rule OTHER_1."""

    def test_utility_function(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(utility_function=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.OTHER
        assert "OTHER_1" in result.triggered_rules

    def test_governance_function(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(governance_function=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.OTHER

    def test_both_utility_and_governance(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(utility_function=True, governance_function=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.OTHER


# --- NON_MICAR classification tests ---


class TestNonMicarClassification:
    """Tests for rule NON_MICAR_1 (NFT exclusion)."""

    def test_nft_unique(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(nft_unique=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.NON_MICAR
        assert "NON_MICAR_1" in result.triggered_rules

    def test_investment_promise_without_whitepaper_not_excluded(
        self, rule_engine: RuleEngine
    ) -> None:
        """Lacking a whitepaper is non-compliance, not scope exclusion."""
        flags = make_flags(investment_promise=True, whitepaper_present=False)
        result = rule_engine.classify(flags)
        # Should NOT be NON_MICAR — missing whitepaper ≠ outside scope
        assert result.micar_class == MiCARClass.NON_CLASSIFIABLE


# --- NON_CLASSIFIABLE fallback ---


class TestNonClassifiable:
    def test_all_false(self, rule_engine: RuleEngine) -> None:
        flags = make_flags(whitepaper_present=False)
        # investment_promise is False, so NON_MICAR_2 won't match
        # and with nothing else, fallback triggers
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.NON_CLASSIFIABLE
        assert "NON_CLASSIFIABLE_FALLBACK" in result.triggered_rules

    def test_only_whitepaper_present(self, rule_engine: RuleEngine) -> None:
        flags = make_flags()  # whitepaper_present=True by default, rest False
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.NON_CLASSIFIABLE


# --- Rule priority tests ---


class TestRulePriority:
    def test_security_before_emt(self, rule_engine: RuleEngine) -> None:
        """Token with both security and EMT characteristics -> SECURITY wins."""
        flags = make_flags(
            regulated_as_security=True,
            investment_promise=True,
            redeemable_in_fiat=True,
            audited_reserves=True,
        )
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.SECURITY

    def test_emt_before_art(self, rule_engine: RuleEngine) -> None:
        """EMT conditions matched but also ART conditions -> EMT wins."""
        flags = make_flags(
            redeemable_in_fiat=True,
            audited_reserves=True,
        )
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.EMT

    def test_art_before_other(self, rule_engine: RuleEngine) -> None:
        """Both ART and utility characteristics -> ART wins."""
        flags = make_flags(backed_by_assets=True, utility_function=True)
        result = rule_engine.classify(flags)
        assert result.micar_class == MiCARClass.ART


# --- Disclosure checklist tests ---


class TestDisclosureChecklist:
    def test_emt_checklist(self, rule_engine: RuleEngine) -> None:
        """EMT: 21 requirements (common + corporate + EMT-specific)."""
        items = rule_engine.get_disclosure_checklist("emt")
        assert len(items) == 21
        ids = [item["id"] for item in items]
        # Common obligations
        assert "whitepaper_present" in ids
        assert "technology_disclosed" in ids
        assert "environmental_impact_disclosed" in ids
        # Corporate identity sub-checks
        assert "legal_entity_named" in ids
        assert "jurisdiction_disclosed" in ids
        assert "regulatory_status_disclosed" in ids
        assert "team_members_identified" in ids
        assert "audit_provider_named" in ids
        # EMT-specific
        assert "redeemable_at_par" in ids

    def test_art_checklist(self, rule_engine: RuleEngine) -> None:
        """ART: 22 requirements (common + corporate + ART-specific)."""
        items = rule_engine.get_disclosure_checklist("art")
        assert len(items) == 22
        ids = [item["id"] for item in items]
        assert "legal_entity_named" in ids
        assert "audit_provider_named" in ids
        assert "reserve_composition_disclosed" in ids
        assert "management_body_statement" in ids

    def test_security_checklist(self, rule_engine: RuleEngine) -> None:
        """Security: 4 items (MiFID II, not MiCAR)."""
        items = rule_engine.get_disclosure_checklist("security")
        assert len(items) == 4
        ids = [item["id"] for item in items]
        assert "micar_excluded" in ids

    def test_other_checklist(self, rule_engine: RuleEngine) -> None:
        """Other: 16 requirements (Art. 6 + Annex I + corporate checks)."""
        items = rule_engine.get_disclosure_checklist("other")
        assert len(items) == 16
        ids = [item["id"] for item in items]
        assert "legal_entity_named" in ids
        assert "jurisdiction_disclosed" in ids
        assert "team_members_identified" in ids
        assert "summary_present" in ids
        assert "management_body_statement" in ids

    def test_non_micar_checklist(self, rule_engine: RuleEngine) -> None:
        items = rule_engine.get_disclosure_checklist("non_micar")
        assert len(items) == 1

    def test_non_classifiable_checklist(self, rule_engine: RuleEngine) -> None:
        items = rule_engine.get_disclosure_checklist("non_classifiable")
        assert len(items) == 1

    def test_unknown_class_raises(self, rule_engine: RuleEngine) -> None:
        with pytest.raises(RuleEngineError, match="No disclosure checklist"):
            rule_engine.get_disclosure_checklist("nonexistent_class")


# --- Engine metadata tests ---


class TestEngineMetadata:
    def test_jurisdiction(self, rule_engine: RuleEngine) -> None:
        assert rule_engine.jurisdiction == "EU-MiCAR"

    def test_version(self, rule_engine: RuleEngine) -> None:
        assert rule_engine.version == "1.0"


# --- Edge cases ---


class TestConditionEvaluation:
    def test_missing_flag_treated_as_none(self, rule_engine: RuleEngine) -> None:
        result = rule_engine.classify({})
        assert result.micar_class == MiCARClass.NON_CLASSIFIABLE

    def test_invalid_rules_dir(self) -> None:
        with pytest.raises(FileNotFoundError):
            RuleEngine(rules_dir=Path("/nonexistent"))
