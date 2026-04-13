"""Structured JSON Lines audit logging for EU AI Act Art. 12 compliance.

Each pipeline run produces an append-only audit entry with:
- Timestamp (UTC ISO 8601)
- Input hash (SHA-256, not the raw text)
- Prompt version (composite hash tag)
- Model identifier
- Full structured output
- Per-stage timing data
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """A single audit log entry for a complete pipeline run."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_hash: str
    prompt_version: str
    model_id: str
    micar_class: str
    compliance_score: float
    fulfilled_count: int
    total_disclosures: int
    triggered_rules: list[str]
    full_output: dict[str, Any] = Field(description="Serialized ComplianceReport.")


class AuditLogger:
    """Append-only JSON Lines audit logger.

    One file per day, stored in the configured audit log directory.
    """

    def __init__(self, log_dir: Path) -> None:
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> Path:
        """Append an audit entry to today's log file.

        Returns:
            The path to the log file written.
        """
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        path = self._log_dir / f"{date_str}.jsonl"
        with path.open("a") as f:
            f.write(entry.model_dump_json() + "\n")
        return path

    def read_entries(self, date_str: str | None = None) -> list[AuditEntry]:
        """Read all entries from a given date's log file.

        Args:
            date_str: Date in ``YYYY-MM-DD`` format. Defaults to today.
        """
        if date_str is None:
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        path = self._log_dir / f"{date_str}.jsonl"
        if not path.exists():
            return []
        entries: list[AuditEntry] = []
        for line in path.read_text().splitlines():
            if line.strip():
                entries.append(AuditEntry.model_validate_json(line))
        return entries
