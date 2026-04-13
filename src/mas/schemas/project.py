"""Project metadata from crypto-asset registries (Searcher Agent output)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectMetadata(BaseModel):
    """Metadata about a crypto-asset project discovered via the Searcher Agent.

    Corresponds to the data collected by the Searcher Agent in Section 3.3
    of the paper, which queries external crypto-asset registries.
    """

    coingecko_id: str = Field(description="CoinGecko coin identifier.")
    name: str = Field(description="Human-readable project name.")
    symbol: str = Field(description="Token ticker symbol (e.g. 'USDT', 'UNI').")
    website_urls: list[str] = Field(
        default_factory=list,
        description="Project homepage URLs.",
    )
    whitepaper_url: str | None = Field(
        default=None,
        description="Direct URL to the project whitepaper, if available.",
    )
    description: str = Field(
        default="",
        description="Short project description from the registry.",
    )
    github_urls: list[str] = Field(
        default_factory=list,
        description="GitHub repository URLs from CoinGecko.",
    )
    contract_addresses: dict[str, str] = Field(
        default_factory=dict,
        description="Chain → contract address mapping (e.g. {'ethereum': '0x...'}).",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="CoinGecko categories (e.g. 'Stablecoins', 'DeFi').",
    )
    market_cap_rank: int | None = Field(
        default=None,
        description="Market capitalization rank, if available.",
    )
