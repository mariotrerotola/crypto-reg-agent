"""Trust & Risk analysis output: trust signals extracted from project documentation.

Each trust signal is scored on a 1-5 scale (higher is better) with evidence
and confidence fields for auditability.  The overall trust score is computed
as a weighted average, and the risk level is determined by deterministic
thresholds — no LLM is involved in the scoring or classification step.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, Field


class TrustSignal(BaseModel):
    """A single trust indicator scored on a 1-5 Likert scale."""

    score: int = Field(
        ge=1,
        le=5,
        description="Trust score: 1=very poor, 2=poor, 3=adequate, 4=good, 5=excellent.",
    )
    evidence: str = Field(
        description=(
            "Direct quote or page reference from the source document "
            "supporting this score."
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM self-reported confidence in this assessment.",
    )


class TrustSignals(BaseModel):
    """Eight trust indicators extracted from project documentation.

    These signals cover the main dimensions of crypto-asset project
    trustworthiness and are used to compute an aggregate trust score.
    """

    team_transparency: TrustSignal = Field(
        description=(
            "Are the team members publicly named with verifiable identities? "
            "Look for named founders, LinkedIn profiles, prior project history, "
            "and accountability structures. Score 5 if fully doxxed team with "
            "verifiable track records; score 1 if completely anonymous."
        ),
    )
    tokenomics_clarity: TrustSignal = Field(
        description=(
            "Is the token supply, distribution, vesting schedule, and allocation "
            "clearly documented? Score 5 if comprehensive tokenomics with "
            "detailed vesting and allocation breakdown; score 1 if no "
            "tokenomics information provided."
        ),
    )
    audit_status: TrustSignal = Field(
        description=(
            "Are smart contract or protocol audits mentioned with named audit "
            "firms? Score 5 if multiple audits by reputable firms (e.g. Trail "
            "of Bits, OpenZeppelin, CertiK); score 1 if no audits mentioned."
        ),
    )
    roadmap_realism: TrustSignal = Field(
        description=(
            "Is the project roadmap concrete with achievable milestones, or "
            "vague and overly ambitious? Score 5 if roadmap has specific, "
            "time-bound deliverables with evidence of past execution; score 1 "
            "if no roadmap or only marketing hype."
        ),
    )
    red_flags_detected: TrustSignal = Field(
        description=(
            "INVERTED SCORING — higher is better. Score 5 if NO red flags "
            "detected; score 1 if MANY red flags found. Red flags include: "
            "guaranteed returns, unrealistic yield promises, Ponzi-like "
            "referral structures, pressure tactics, fake partnerships, "
            "plagiarised whitepaper content."
        ),
    )
    technical_depth: TrustSignal = Field(
        description=(
            "Does the documentation show genuine technical substance? Score 5 "
            "if whitepaper contains detailed protocol design, cryptographic "
            "proofs, consensus mechanisms; score 1 if only marketing copy "
            "with no technical content."
        ),
    )
    funding_transparency: TrustSignal = Field(
        description=(
            "Is the use of raised funds (ICO, token sale, treasury) described? "
            "Score 5 if detailed fund allocation and treasury management are "
            "documented; score 1 if no information on fund usage."
        ),
    )
    community_governance: TrustSignal = Field(
        description=(
            "Are governance mechanisms described (DAO voting, proposal process, "
            "on-chain governance)? Score 5 if comprehensive governance with "
            "on-chain voting and active participation; score 1 if fully "
            "centralised with no governance mechanisms."
        ),
    )


class RiskLevel(StrEnum):
    """Deterministic risk classification based on trust score thresholds."""

    HIGH_RISK = "high_risk"
    ELEVATED = "elevated"
    MODERATE = "moderate"
    LOW_RISK = "low_risk"


class TrustAnalysisResult(BaseModel):
    """Aggregate trust & risk assessment combining LLM-extracted signals
    with deterministic scoring and risk classification.
    """

    # Weights for the weighted-average trust score.
    SIGNAL_WEIGHTS: ClassVar[dict[str, float]] = {
        "team_transparency": 1.5,
        "tokenomics_clarity": 1.5,
        "audit_status": 1.5,
        "roadmap_realism": 1.0,
        "red_flags_detected": 2.0,
        "technical_depth": 1.0,
        "funding_transparency": 1.0,
        "community_governance": 0.5,
    }

    signals: TrustSignals
    overall_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Weighted trust score as a percentage (0-100).",
    )
    contract_modifier: float = Field(
        default=0.0,
        description="On-chain security modifier from GoPlus (-30 to +10).",
    )
    risk_level: RiskLevel
    disclaimer: str = Field(
        default=(
            "This trust & risk assessment is informational only and does NOT "
            "constitute investment, financial, or legal advice."
        ),
    )

    @staticmethod
    def compute_score(signals: TrustSignals) -> float:
        """Weighted average: sum(w_i * s_i) / sum(w_i * 5) * 100."""
        weights = TrustAnalysisResult.SIGNAL_WEIGHTS
        weighted_sum = 0.0
        weight_total = 0.0
        for name, weight in weights.items():
            signal: TrustSignal = getattr(signals, name)
            weighted_sum += weight * signal.score
            weight_total += weight * 5  # max possible per signal
        return round(weighted_sum / weight_total * 100, 2) if weight_total > 0 else 0.0

    @staticmethod
    def classify_risk(score: float) -> RiskLevel:
        """Deterministic risk classification from score thresholds."""
        if score >= 75:
            return RiskLevel.LOW_RISK
        if score >= 55:
            return RiskLevel.MODERATE
        if score >= 35:
            return RiskLevel.ELEVATED
        return RiskLevel.HIGH_RISK
