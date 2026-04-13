"""Tests for the SEC jurisdiction rule set.

Demonstrates that the rule engine is genuinely jurisdiction-swappable:
the same engine class, same flag schema, same evaluation logic — different
YAML rules, different classification taxonomy.

Rules based on:
  - Howey Test (SEC v. W.J. Howey Co., 1946)
  - Securities Act of 1933 § 2(a)(1)
  - SEC FinHub Framework (April 2019)
"""

from __future__ import annotations

from mas.rules.engine import RuleEngine
from mas.schemas.classification import MiCARClass
from tests.conftest import make_flags


class TestSECMetadata:
    def test_jurisdiction(self, sec_engine: RuleEngine) -> None:
        assert sec_engine.jurisdiction == "US-SEC"

    def test_version(self, sec_engine: RuleEngine) -> None:
        assert sec_engine.version == "0.2"


class TestHoweyClassification:
    def test_full_howey(self, sec_engine: RuleEngine) -> None:
        """All Howey prongs: transferable + investment promise + reserves, no governance."""
        flags = make_flags(
            rights_transferable=True,
            investment_promise=True,
            reserve_assets_held=True,
        )
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "investment_contract"
        assert result.jurisdiction == "US-SEC"
        assert "HOWEY_FULL" in result.triggered_rules
        assert result.micar_class == MiCARClass.SECURITY

    def test_howey_with_dividends(self, sec_engine: RuleEngine) -> None:
        """Howey via dividend-like returns instead of reserves."""
        flags = make_flags(
            rights_transferable=True,
            investment_promise=True,
            dividend_like=True,
        )
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "investment_contract"

    def test_howey_blocked_by_governance(self, sec_engine: RuleEngine) -> None:
        """Per FinHub: governance → sufficient decentralization → not Howey."""
        flags = make_flags(
            rights_transferable=True,
            investment_promise=True,
            reserve_assets_held=True,
            governance_function=True,
        )
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class != "investment_contract"

    def test_howey_marketing_pattern(self, sec_engine: RuleEngine) -> None:
        """SEC v. Telegram pattern: security language + investment + dividends."""
        flags = make_flags(
            investment_promise=True,
            dividend_like=True,
            security_language=True,
        )
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "investment_contract"
        assert "HOWEY_MARKETING" in result.triggered_rules

    def test_missing_investment_promise_not_howey(self, sec_engine: RuleEngine) -> None:
        """No investment promise → cannot satisfy Howey prong 3."""
        flags = make_flags(
            rights_transferable=True,
            reserve_assets_held=True,
            dividend_like=True,
        )
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class != "investment_contract"


class TestTraditionalSecurity:
    def test_equity(self, sec_engine: RuleEngine) -> None:
        flags = make_flags(represents_equity=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "security"
        assert "SEC_EQUITY" in result.triggered_rules

    def test_capital_rights(self, sec_engine: RuleEngine) -> None:
        flags = make_flags(has_capital_rights=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "security"

    def test_debt(self, sec_engine: RuleEngine) -> None:
        flags = make_flags(represents_debt=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "security"
        assert "SEC_DEBT" in result.triggered_rules

    def test_explicitly_regulated(self, sec_engine: RuleEngine) -> None:
        flags = make_flags(regulated_as_security=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "security"
        assert "SEC_EXPLICIT" in result.triggered_rules


class TestCommodity:
    def test_utility_no_investment(self, sec_engine: RuleEngine) -> None:
        """Utility token without investment characteristics → commodity."""
        flags = make_flags(utility_function=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "commodity"
        assert "COMMODITY_UTILITY" in result.triggered_rules
        assert result.micar_class == MiCARClass.NON_MICAR

    def test_governance_no_investment(self, sec_engine: RuleEngine) -> None:
        flags = make_flags(governance_function=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "commodity"

    def test_utility_with_investment_not_commodity(self, sec_engine: RuleEngine) -> None:
        """Utility + investment promise → fails none condition → not commodity."""
        flags = make_flags(utility_function=True, investment_promise=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class != "commodity"

    def test_utility_with_security_language_not_commodity(self, sec_engine: RuleEngine) -> None:
        """Per FinHub: utility token marketed as investment → not commodity."""
        flags = make_flags(utility_function=True, security_language=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class != "commodity"


class TestNFT:
    def test_nft_no_investment(self, sec_engine: RuleEngine) -> None:
        """Unique NFT without investment promise → non_security_nft."""
        flags = make_flags(nft_unique=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "non_security_nft"
        assert "NFT_EXEMPT" in result.triggered_rules

    def test_nft_with_investment_promise(self, sec_engine: RuleEngine) -> None:
        """NFT marketed as investment → NOT exempt (could be security)."""
        flags = make_flags(nft_unique=True, investment_promise=True)
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class != "non_security_nft"


class TestFallback:
    def test_no_indicators(self, sec_engine: RuleEngine) -> None:
        flags = make_flags()
        result = sec_engine.classify(flags)
        assert result.jurisdiction_class == "non_classifiable"
        assert "UNCLASSIFIED_FALLBACK" in result.triggered_rules


class TestSECDisclosures:
    def test_investment_contract_checklist(self, sec_engine: RuleEngine) -> None:
        checklist = sec_engine.get_disclosure_checklist("investment_contract")
        assert len(checklist) == 9
        ids = [item["id"] for item in checklist]
        assert "registration_or_exemption" in ids
        assert "risk_factors" in ids
        assert "use_of_proceeds" in ids
        assert "decentralization_status" in ids
        assert "technology_description" in ids

    def test_security_checklist(self, sec_engine: RuleEngine) -> None:
        checklist = sec_engine.get_disclosure_checklist("security")
        assert len(checklist) == 5

    def test_commodity_checklist(self, sec_engine: RuleEngine) -> None:
        checklist = sec_engine.get_disclosure_checklist("commodity")
        assert len(checklist) == 3
        ids = [item["id"] for item in checklist]
        assert "no_investment_marketing" in ids

    def test_nft_checklist(self, sec_engine: RuleEngine) -> None:
        checklist = sec_engine.get_disclosure_checklist("non_security_nft")
        assert len(checklist) == 2

    def test_all_items_have_article_references(self, sec_engine: RuleEngine) -> None:
        for cls in ["investment_contract", "security", "commodity", "non_security_nft"]:
            checklist = sec_engine.get_disclosure_checklist(cls)
            for item in checklist:
                assert "article" in item, f"{cls}/{item['id']} missing article"
                assert item["article"] != "", f"{cls}/{item['id']} empty article"


class TestRulePriority:
    def test_howey_before_traditional_equity(self, sec_engine: RuleEngine) -> None:
        """Howey test triggers before traditional equity classification."""
        flags = make_flags(
            rights_transferable=True,
            investment_promise=True,
            reserve_assets_held=True,
            represents_equity=True,
        )
        result = sec_engine.classify(flags)
        assert "HOWEY_FULL" in result.triggered_rules
        assert result.jurisdiction_class == "investment_contract"


class TestCrossJurisdiction:
    def test_same_utility_flags_different_results(
        self, rule_engine: RuleEngine, sec_engine: RuleEngine
    ) -> None:
        """Same flags produce different classifications under EU vs US."""
        flags = make_flags(utility_function=True, governance_function=True)

        eu_result = rule_engine.classify(flags)
        us_result = sec_engine.classify(flags)

        assert eu_result.jurisdiction == "EU-MiCAR"
        assert eu_result.micar_class == MiCARClass.OTHER
        assert eu_result.jurisdiction_class == "other"

        assert us_result.jurisdiction == "US-SEC"
        assert us_result.jurisdiction_class == "commodity"

    def test_same_investment_flags_both_security(
        self, rule_engine: RuleEngine, sec_engine: RuleEngine
    ) -> None:
        """Investment promise + equity → security in both jurisdictions."""
        flags = make_flags(
            represents_equity=True,
            investment_promise=True,
        )

        eu_result = rule_engine.classify(flags)
        us_result = sec_engine.classify(flags)

        # Both classify as security, but through different rules
        assert eu_result.micar_class == MiCARClass.SECURITY
        assert us_result.micar_class == MiCARClass.SECURITY
        assert eu_result.triggered_rules != us_result.triggered_rules
