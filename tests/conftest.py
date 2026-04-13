"""Shared test fixtures."""

from pathlib import Path

import pytest

from mas.rules.engine import RuleEngine

RULES_DIR = Path(__file__).parent.parent / "src" / "mas" / "rules" / "micar_v1"


@pytest.fixture
def rule_engine() -> RuleEngine:
    """Rule engine loaded with MiCAR v1 rules."""
    return RuleEngine(rules_dir=RULES_DIR)


def make_flags(**overrides: bool) -> dict[str, bool]:
    """Create a flags dict with all False defaults. Override specific flags."""
    defaults: dict[str, bool] = {
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
    return defaults
