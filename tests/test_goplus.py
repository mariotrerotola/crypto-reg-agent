"""Tests for the GoPlus Security client."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from mas.agents.goplus import ContractSecurity, GoPlusClient


def _make_security(**overrides: Any) -> ContractSecurity:
    """Create a ContractSecurity with safe defaults."""
    defaults: dict[str, Any] = {
        "chain": "ethereum",
        "address": "0x1234",
        "is_honeypot": False,
        "is_open_source": True,
        "is_proxy": False,
        "is_mintable": False,
        "hidden_owner": False,
        "can_take_back_ownership": False,
        "owner_change_balance": False,
        "transfer_pausable": False,
        "is_blacklisted": False,
        "selfdestruct": False,
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "holder_count": 1000,
        "trust_list": False,
    }
    defaults.update(overrides)
    return ContractSecurity(**defaults)


class TestTrustModifier:
    def test_clean_verified_contract(self) -> None:
        sec = _make_security(is_open_source=True, holder_count=5000)
        mod = sec.trust_modifier()
        assert mod > 0  # Bonus for verified + many holders

    def test_honeypot_max_penalty(self) -> None:
        sec = _make_security(is_honeypot=True)
        assert sec.trust_modifier() == -30.0

    def test_hidden_owner_penalty(self) -> None:
        sec = _make_security(hidden_owner=True)
        mod = sec.trust_modifier()
        assert mod < 0

    def test_high_sell_tax(self) -> None:
        sec = _make_security(sell_tax=15.0)
        mod = sec.trust_modifier()
        assert mod <= -5

    def test_closed_source_penalty(self) -> None:
        sec = _make_security(is_open_source=False)
        mod = sec.trust_modifier()
        assert mod < 0

    def test_trust_list_bonus(self) -> None:
        sec = _make_security(trust_list=True, holder_count=5000)
        mod = sec.trust_modifier()
        assert mod > 5  # verified + trust list + holders

    def test_modifier_bounded(self) -> None:
        """Modifier never exceeds [-30, +10] range."""
        # Max penalties
        worst = _make_security(
            is_honeypot=True,
            hidden_owner=True,
            owner_change_balance=True,
        )
        assert worst.trust_modifier() >= -30.0

        # Max bonuses
        best = _make_security(
            is_open_source=True,
            trust_list=True,
            holder_count=100000,
        )
        assert best.trust_modifier() <= 10.0


class TestRedFlagCount:
    def test_no_flags(self) -> None:
        sec = _make_security()
        assert sec.red_flag_count == 0

    def test_honeypot_is_red_flag(self) -> None:
        sec = _make_security(is_honeypot=True)
        assert sec.red_flag_count >= 1

    def test_multiple_red_flags(self) -> None:
        sec = _make_security(
            is_honeypot=True,
            hidden_owner=True,
            owner_change_balance=True,
        )
        assert sec.red_flag_count == 3


class TestWarningCount:
    def test_clean_contract(self) -> None:
        sec = _make_security()
        assert sec.warning_count == 0

    def test_mintable_is_warning(self) -> None:
        sec = _make_security(is_mintable=True)
        assert sec.warning_count >= 1

    def test_proxy_is_warning(self) -> None:
        sec = _make_security(is_proxy=True)
        assert sec.warning_count >= 1


class TestGoPlusAPI:
    def test_unsupported_chain(self) -> None:
        client = GoPlusClient(timeout=5.0)
        result = client.check_token("unknown_chain", "0x1234")
        assert result is None

    def test_evm_api_error(self) -> None:
        import httpx

        client = GoPlusClient(timeout=5.0)
        client._client = MagicMock()
        client._client.get = MagicMock(side_effect=httpx.HTTPError("timeout"))

        result = client.check_token("ethereum", "0x1234")
        assert result is None

    def test_evm_empty_result(self) -> None:
        client = GoPlusClient(timeout=5.0)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {}}
        mock_resp.raise_for_status = MagicMock()
        client._client = MagicMock()
        client._client.get = MagicMock(return_value=mock_resp)

        result = client.check_token("ethereum", "0x1234")
        assert result is None

    def test_evm_parses_response(self) -> None:
        client = GoPlusClient(timeout=5.0)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "0x1234": {
                    "is_honeypot": "0",
                    "is_open_source": "1",
                    "is_proxy": "0",
                    "is_mintable": "1",
                    "hidden_owner": "0",
                    "can_take_back_ownership": "0",
                    "owner_change_balance": "0",
                    "transfer_pausable": "0",
                    "is_blacklisted": "0",
                    "selfdestruct": "0",
                    "buy_tax": "0",
                    "sell_tax": "0.05",
                    "holder_count": "500",
                    "trust_list": "0",
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        client._client = MagicMock()
        client._client.get = MagicMock(return_value=mock_resp)

        result = client.check_token("ethereum", "0x1234")
        assert result is not None
        assert result.is_honeypot is False
        assert result.is_open_source is True
        assert result.is_mintable is True
        assert result.sell_tax == 5.0  # 0.05 * 100
        assert result.holder_count == 500

    def test_solana_api_error(self) -> None:
        import httpx

        client = GoPlusClient(timeout=5.0)
        client._client = MagicMock()
        client._client.get = MagicMock(side_effect=httpx.HTTPError("timeout"))

        result = client.check_token("solana", "So1111")
        assert result is None
