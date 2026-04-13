"""Final aggregate output from the full compliance analysis pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from mas.agents.goplus import ContractSecurity
from mas.schemas.asset_flags import AssetFlags
from mas.schemas.classification import ClassificationResult
from mas.schemas.compliance_flags import ComplianceFlags
from mas.schemas.trust_analysis import TrustAnalysisResult


class ComplianceReport(BaseModel):
    """Complete output of the 3-stage compliance analysis pipeline.

    The ``compliance_score`` is computed automatically from the disclosure
    verification results, implementing Equation 2 from the paper:
    ``score = fulfilled_disclosures / applicable_disclosures``.
    """

    input_hash: str = Field(description="SHA-256 hex digest of the input text.")
    timestamp: datetime
    prompt_version: str = Field(description="Composite prompt version tag for audit trail.")
    model_id: str = Field(description="LLM model identifier used for extraction.")

    asset_flags: AssetFlags
    classification: ClassificationResult
    compliance_flags: ComplianceFlags
    trust_analysis: TrustAnalysisResult | None = Field(
        default=None,
        description="Trust & risk assessment results, if trust analysis was enabled.",
    )
    contract_security: ContractSecurity | None = Field(
        default=None,
        description="On-chain contract security analysis from GoPlus.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def compliance_score(self) -> float:
        """Equation 2: fulfilled / applicable disclosures."""
        total = len(self.compliance_flags.disclosures)
        if total == 0:
            return 0.0
        fulfilled = sum(1 for d in self.compliance_flags.disclosures if d.fulfilled)
        return round(fulfilled / total, 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fulfilled_count(self) -> int:
        """Number of disclosure requirements fulfilled."""
        return sum(1 for d in self.compliance_flags.disclosures if d.fulfilled)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_disclosures(self) -> int:
        """Total number of applicable disclosure requirements."""
        return len(self.compliance_flags.disclosures)
