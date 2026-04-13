"""GoPlus Security API client for on-chain contract analysis.

Queries the GoPlus Security API (free, no key required) to detect
scam patterns in smart contracts: honeypots, hidden taxes, owner
privileges, and other red flags that cannot be identified from
documentation alone.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from mas.agents.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

GOPLUS_BASE = "https://api.gopluslabs.io/api/v1"

# Chain name → GoPlus chain ID
CHAIN_IDS: dict[str, str] = {
    "ethereum": "1",
    "eth": "1",
    "bsc": "56",
    "binance-smart-chain": "56",
    "polygon-pos": "137",
    "polygon": "137",
    "arbitrum-one": "42161",
    "arbitrum": "42161",
    "optimistic-ethereum": "10",
    "optimism": "10",
    "avalanche": "43114",
    "avax": "43114",
    "base": "8453",
    "fantom": "250",
    "cronos": "25",
}

SOLANA_CHAINS = {"solana", "sol"}


class ContractSecurity(BaseModel):
    """On-chain security analysis result from GoPlus."""

    chain: str = Field(description="Blockchain network.")
    address: str = Field(description="Contract address.")

    # Core safety signals (0 = safe, 1 = dangerous)
    is_honeypot: bool = Field(default=False, description="Cannot sell after buying.")
    is_open_source: bool = Field(default=False, description="Contract source verified.")
    is_proxy: bool = Field(default=False, description="Upgradeable proxy contract.")
    is_mintable: bool = Field(default=False, description="Owner can mint new tokens.")
    hidden_owner: bool = Field(default=False, description="Ownership hidden.")
    can_take_back_ownership: bool = Field(
        default=False, description="Owner can reclaim ownership."
    )
    owner_change_balance: bool = Field(
        default=False, description="Owner can modify balances."
    )
    transfer_pausable: bool = Field(
        default=False, description="Transfers can be paused."
    )
    is_blacklisted: bool = Field(
        default=False, description="Has blacklist functionality."
    )
    selfdestruct: bool = Field(
        default=False, description="Contract can self-destruct."
    )

    # Tax
    buy_tax: float = Field(default=0.0, description="Buy tax percentage.")
    sell_tax: float = Field(default=0.0, description="Sell tax percentage.")

    # Holder info
    holder_count: int = Field(default=0, description="Number of token holders.")

    # Trust
    trust_list: bool = Field(
        default=False, description="Token is on GoPlus trust list."
    )

    @property
    def red_flag_count(self) -> int:
        """Count critical red flags."""
        flags = [
            self.is_honeypot,
            self.hidden_owner,
            self.can_take_back_ownership,
            self.owner_change_balance,
            self.selfdestruct,
            self.buy_tax > 10,
            self.sell_tax > 10,
        ]
        return sum(flags)

    @property
    def warning_count(self) -> int:
        """Count warnings (not critical but concerning)."""
        flags = [
            self.is_mintable,
            self.is_proxy,
            self.transfer_pausable,
            self.is_blacklisted,
            not self.is_open_source,
            self.buy_tax > 0 and self.buy_tax <= 10,
            self.sell_tax > 0 and self.sell_tax <= 10,
        ]
        return sum(flags)

    def trust_modifier(self) -> float:
        """Compute a trust score modifier (-30 to +10).

        Applied as a bonus/malus to the LLM-based trust score.
        """
        if self.is_honeypot:
            return -30.0

        modifier = 0.0

        # Red flags: heavy penalties
        if self.hidden_owner:
            modifier -= 10.0
        if self.owner_change_balance:
            modifier -= 10.0
        if self.can_take_back_ownership:
            modifier -= 8.0
        if self.selfdestruct:
            modifier -= 8.0

        # Tax penalties
        if self.sell_tax > 10:
            modifier -= 10.0
        elif self.sell_tax > 5:
            modifier -= 5.0
        elif self.sell_tax > 0:
            modifier -= 2.0

        if self.buy_tax > 10:
            modifier -= 5.0

        # Warnings: lighter penalties
        if self.is_mintable:
            modifier -= 3.0
        if self.is_proxy:
            modifier -= 2.0
        if not self.is_open_source:
            modifier -= 5.0

        # Bonuses
        if self.is_open_source and not self.is_proxy:
            modifier += 5.0
        if self.trust_list:
            modifier += 5.0
        if self.holder_count > 1000:
            modifier += 3.0

        return max(-30.0, min(10.0, modifier))


class GoPlusClient:
    """Client for the GoPlus Security API (free, no key required).

    Args:
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, timeout: float = 15.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._rate_limiter = RateLimiter(min_interval=0.5)

    def check_token(self, chain: str, address: str) -> ContractSecurity | None:
        """Check a token contract for security issues.

        Args:
            chain: Chain name (e.g. 'ethereum', 'bsc', 'solana').
            address: Contract address.

        Returns:
            ContractSecurity with analysis results, or None if lookup fails.
        """
        chain_lower = chain.lower()

        if chain_lower in SOLANA_CHAINS:
            return self._check_solana(address)

        chain_id = CHAIN_IDS.get(chain_lower)
        if not chain_id:
            logger.warning("GoPlus: unsupported chain '%s'", chain)
            return None

        return self._check_evm(chain_id, chain_lower, address)

    def _check_evm(
        self, chain_id: str, chain: str, address: str
    ) -> ContractSecurity | None:
        """Check an EVM-compatible token."""
        self._rate_limiter.wait()
        try:
            resp = self._client.get(
                f"{GOPLUS_BASE}/token_security/{chain_id}",
                params={"contract_addresses": address.lower()},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("GoPlus: API error for %s on chain %s: %s", address, chain, e)
            return None

        result = data.get("result", {})
        token_data: dict[str, Any] = result.get(address.lower(), {})
        if not token_data:
            logger.warning("GoPlus: no data for %s on chain %s", address, chain)
            return None

        return ContractSecurity(
            chain=chain,
            address=address,
            is_honeypot=token_data.get("is_honeypot") == "1",
            is_open_source=token_data.get("is_open_source") == "1",
            is_proxy=token_data.get("is_proxy") == "1",
            is_mintable=token_data.get("is_mintable") == "1",
            hidden_owner=token_data.get("hidden_owner") == "1",
            can_take_back_ownership=token_data.get("can_take_back_ownership") == "1",
            owner_change_balance=token_data.get("owner_change_balance") == "1",
            transfer_pausable=token_data.get("transfer_pausable") == "1",
            is_blacklisted=token_data.get("is_blacklisted") == "1",
            selfdestruct=token_data.get("selfdestruct") == "1",
            buy_tax=float(token_data.get("buy_tax", 0) or 0) * 100,
            sell_tax=float(token_data.get("sell_tax", 0) or 0) * 100,
            holder_count=int(token_data.get("holder_count", 0) or 0),
            trust_list=token_data.get("trust_list") == "1",
        )

    def _check_solana(self, address: str) -> ContractSecurity | None:
        """Check a Solana token (limited fields available)."""
        self._rate_limiter.wait()
        try:
            resp = self._client.get(
                f"{GOPLUS_BASE}/solana/token_security",
                params={"contract_addresses": address},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("GoPlus: Solana API error for %s: %s", address, e)
            return None

        result = data.get("result", {})
        token_data: dict[str, Any] = result.get(address, {})
        if not token_data:
            logger.warning("GoPlus: no Solana data for %s", address)
            return None

        return ContractSecurity(
            chain="solana",
            address=address,
            is_open_source=True,  # Solana programs are always visible
            holder_count=int(token_data.get("holder_count", 0) or 0),
            trust_list=token_data.get("trusted_token") == "1"
            or token_data.get("trusted_token") == 1,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
