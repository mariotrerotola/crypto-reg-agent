"""Tests for audit logging."""

from pathlib import Path

import pytest

from mas.audit.logger import AuditEntry, AuditLogger


@pytest.fixture
def audit_logger(tmp_path: Path) -> AuditLogger:
    return AuditLogger(log_dir=tmp_path / "audit")


def _make_entry() -> AuditEntry:
    return AuditEntry(
        input_hash="abc123def456",
        prompt_version="v1|asset_flags:1234|compliance:5678",
        model_id="gpt-4o",
        micar_class="e_money_token",
        compliance_score=0.75,
        fulfilled_count=6,
        total_disclosures=8,
        triggered_rules=["EMT_1"],
        full_output={"test": "data"},
    )


class TestAuditLogger:
    def test_log_creates_file(self, audit_logger: AuditLogger) -> None:
        entry = _make_entry()
        path = audit_logger.log(entry)
        assert path.exists()
        assert path.suffix == ".jsonl"

    def test_log_appends(self, audit_logger: AuditLogger) -> None:
        audit_logger.log(_make_entry())
        audit_logger.log(_make_entry())
        entries = audit_logger.read_entries()
        assert len(entries) == 2

    def test_read_entries_empty(self, audit_logger: AuditLogger) -> None:
        entries = audit_logger.read_entries("2020-01-01")
        assert entries == []

    def test_round_trip(self, audit_logger: AuditLogger) -> None:
        entry = _make_entry()
        audit_logger.log(entry)
        entries = audit_logger.read_entries()
        assert len(entries) == 1
        restored = entries[0]
        assert restored.input_hash == entry.input_hash
        assert restored.model_id == entry.model_id
        assert restored.compliance_score == entry.compliance_score
        assert restored.triggered_rules == entry.triggered_rules

    def test_creates_dir(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "nested" / "audit"
        AuditLogger(log_dir=log_dir)
        assert log_dir.exists()


class TestAuditEntry:
    def test_timestamp_default(self) -> None:
        entry = _make_entry()
        assert entry.timestamp is not None

    def test_json_serialization(self) -> None:
        entry = _make_entry()
        json_str = entry.model_dump_json()
        restored = AuditEntry.model_validate_json(json_str)
        assert restored.input_hash == entry.input_hash
