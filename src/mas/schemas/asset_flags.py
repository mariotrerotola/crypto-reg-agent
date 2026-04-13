"""Stage 1 output: classification flags extracted from project documentation.

Flags and descriptions are reproduced verbatim from Listing A5 / Table A2
of the paper. Each flag carries its boolean value plus evidence and confidence
fields added for auditability (MVP extension over the paper's bare bools).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssetFlag(BaseModel):
    """A single boolean flag with evidence citation."""

    value: bool
    evidence: str = Field(
        description=(
            "Direct quote or page reference from the source document supporting this flag value."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM self-reported confidence in this extraction.",
    )


class AssetFlags(BaseModel):
    """Classification indicators extracted from website content for initial
    MiCAR asset type determination.

    These flags are used by classify_by_flags() to determine the preliminary
    asset classification (EMT, ART, SECURITY, OTHER, NON_MICAR,
    NON_CLASSIFIABLE) before detailed compliance evaluation.

    Flag names and descriptions from Listing A5 / Table A2 of the paper.
    """

    # Security classification flags — primary indicators
    regulated_as_security: AssetFlag = Field(
        description=(
            "The asset is classified under regulatory frameworks governing "
            "securities, meaning it must comply with legal requirements "
            "pertaining to investor protection, disclosure, and reporting "
            "obligations."
        )
    )
    represents_equity: AssetFlag = Field(
        description=(
            "The asset confers ownership rights or a share in the profits of "
            "an underlying entity, resembling traditional equity instruments "
            "such as shares or stock."
        )
    )
    represents_debt: AssetFlag = Field(
        description=(
            "The asset represents a financial obligation of an issuer to "
            "repay a debt, akin to traditional debt securities such as bonds "
            "or promissory notes."
        )
    )
    has_capital_rights: AssetFlag = Field(
        description=(
            "The asset grants the holder certain rights over the capital "
            "structure of an entity, including claims to dividends, profits, "
            "or liquidation proceeds, similar to ownership stakes."
        )
    )
    investment_promise: AssetFlag = Field(
        description=(
            "The asset is marketed with the promise of financial returns, "
            "suggesting an investment opportunity. This implies potential "
            "regulatory scrutiny for compliance with securities laws."
        )
    )
    dividend_like: AssetFlag = Field(
        description=(
            "The asset offers returns or benefits similar to dividends, which "
            "are typically distributed by equity holders of a company, "
            "signaling investment-like characteristics."
        )
    )
    security_language: AssetFlag = Field(
        description=(
            "The marketing or contractual terms of the asset use terminology "
            'commonly associated with securities, such as "shares," "equity," '
            'or "interest," which may trigger regulatory requirements for '
            "registration and oversight."
        )
    )
    rights_transferable: AssetFlag = Field(
        description=(
            "The asset can be freely transferred, often implying liquidity "
            "and tradability, similar to financial instruments that are "
            "exchanged in secondary markets."
        )
    )

    # EMT (E-Money Token) classification flags
    redeemable_in_fiat: AssetFlag = Field(
        description=(
            "The asset can be converted or redeemed for a fiat currency, "
            "providing a clear value exchange mechanism, which is typical "
            "for stablecoins or other forms of currency-backed assets."
        )
    )
    daily_redeemability: AssetFlag = Field(
        description=(
            "The asset can be redeemed or exchanged daily, providing "
            "liquidity and flexibility to investors, which is a critical "
            "characteristic for money market instruments."
        )
    )
    reserve_assets_held: AssetFlag = Field(
        description=(
            "The issuer holds a reserve of assets backing the issued tokens "
            "or units, providing security to investors by ensuring that the "
            "asset is backed by tangible assets, similar to collateralization "
            "in financial markets."
        )
    )
    audited_reserves: AssetFlag = Field(
        description=(
            "The reserves held by the issuer are subject to independent "
            "audits, enhancing transparency and trust by confirming that the "
            "issuer maintains sufficient reserves to back the value of the "
            "asset."
        )
    )
    redemption_policy_clear: AssetFlag = Field(
        description=(
            "The asset has a clearly defined process for redemption, ensuring "
            "that investors can easily exchange or liquidate their holdings, "
            "similar to the redemption terms for traditional securities."
        )
    )

    # ART (Asset-Referenced Token) classification flags
    backed_by_assets: AssetFlag = Field(
        description=(
            "The asset is anchored to a basket of assets (currencies, "
            "commodities, cryptocurrencies), providing value stabilization "
            "through diversified collateral, a characteristic of "
            "asset-referenced tokens."
        )
    )

    # OTHER (Utility/Governance token) classification flags
    utility_function: AssetFlag = Field(
        description=(
            "The asset provides access to services, platforms, or ecosystem "
            "features, representing a utility token that grants functional "
            "rights rather than investment returns."
        )
    )
    governance_function: AssetFlag = Field(
        description=(
            "The asset confers governance or voting rights in a decentralized "
            "protocol or organization, allowing holders to participate in "
            "decision-making processes."
        )
    )

    # NFT classification flag
    nft_unique: AssetFlag = Field(
        description=(
            "The asset is a unique or non-fungible token (NFT), representing "
            "a one-of-a-kind digital asset rather than a fungible currency "
            "or security."
        )
    )

    # General documentation and compliance indicators
    whitepaper_present: AssetFlag = Field(
        description=(
            "The asset has a formal whitepaper or investment prospectus, "
            "which is critical for providing transparency and detailed "
            "information about the asset's structure, risks, and potential "
            "returns."
        )
    )
    disclaimers_regulatory: AssetFlag = Field(
        description=(
            "The asset's documentation includes regulatory warnings or "
            "references to financial regulations, indicating awareness of "
            "compliance requirements and investor protection obligations."
        )
    )

    def to_bool_dict(self) -> dict[str, bool]:
        """Return a flat dict of flag_name -> bool for the rule engine."""
        return {name: getattr(self, name).value for name in type(self).model_fields}
