# EU AI Act Compliance Mapping

This document maps the MiCAR Compliance Agent's design to the
requirements of Regulation (EU) 2024/1689 (EU AI Act), specifically
the provisions applicable to high-risk AI systems (Title III, Chapter 2,
Articles 9-15).

The system is designed as a **decision-support tool** for compliance
analysts, not an autonomous decision-making system. All outputs are
advisory and require human review before regulatory action.

## Applicability Assessment

Under the EU AI Act, AI systems used to assist public authorities
in administrative or regulatory decision-making may fall within the
high-risk category (Annex III, point 8 — administration of justice
and democratic processes). Even where the system operates as a
research prototype, the architecture proactively addresses high-risk
requirements to demonstrate regulatory awareness and production
readiness.

High-risk provisions (Articles 9-15) apply from **2 August 2026**.

## Article-by-Article Mapping

### Article 9 — Risk Management System

| Requirement | Implementation |
|-------------|---------------|
| Identification of known and foreseeable risks | Trust & Risk Indicators module identifies 8 risk dimensions; GoPlus checks on-chain scam patterns |
| Risk estimation and evaluation | Weighted trust scoring (0-100%) with deterministic risk classification thresholds |
| Residual risk management | Disclaimer on all outputs: "does NOT constitute investment, financial, or legal advice" |
| Testing measures | 160 automated tests covering classification rules, scoring logic, and pipeline integration |

### Article 10 — Data and Data Governance

| Requirement | Implementation |
|-------------|---------------|
| Training data quality | Not applicable — no model fine-tuning. Uses pre-trained GPT-4o via API |
| Input data relevance | Asset flags derived from paper's peer-reviewed taxonomy (Listing A5, Table A2) |
| Bias examination | Classification rules are deterministic YAML — auditable, no learned bias |
| Data provenance | `crawled_urls` field tracks every source; `input_hash` (SHA-256) ensures reproducibility |

### Article 11 — Technical Documentation

| Requirement | Implementation |
|-------------|---------------|
| General description of the system | [README.md](../README.md), [architecture.md](architecture.md) |
| Design specifications | LangGraph StateGraph with documented node factories and state schema |
| Monitoring and operation | `MAS_` environment variables for configuration; Streamlit UI for interactive use |
| Risk management information | Trust score methodology documented in [architecture.md](architecture.md) |
| Change log | Git commit history; YAML rule versions tracked (`version` field in each rule file) |

### Article 12 — Record-Keeping (Logging)

| Requirement | Implementation |
|-------------|---------------|
| Automatic logging of events | `AuditLogger` writes JSON Lines to `audit_log_dir` with timestamps |
| Traceability of operation | Each report includes `input_hash`, `prompt_version`, `model_id`, `timestamp` |
| Monitoring of operation | `prompt_version_tag()` hashes all prompt files — any modification is detectable |
| Log retention | JSONL append-only files; retention policy configurable by deployer |

**Audit entry fields:**
- `timestamp` (ISO 8601)
- `input_hash` (SHA-256)
- `prompt_version` (composite hash of all prompt files)
- `model_id` (e.g. `gpt-4o`)
- `classification` result
- `compliance_score`

### Article 13 — Transparency and Provision of Information

| Requirement | Implementation |
|-------------|---------------|
| Understandable output | Reports include `triggered_rules`, `explanation`, and per-flag `evidence` |
| Intended purpose | README, docstrings, and CLI help clearly state the system is a compliance analysis tool |
| Level of accuracy | Confidence scores (0.0-1.0) on every extracted flag and disclosure check |
| Known limitations | Not validated on a labeled dataset; classification accuracy depends on LLM extraction quality |
| Human oversight measures | All outputs are advisory; no automated enforcement actions |

**Explainability chain:**
```
whitepaper text
  → 19 AssetFlags (each with evidence quote + confidence)
    → classification rule ID + explanation
      → per-disclosure fulfilled/not-fulfilled + evidence
        → trust signals (each with evidence + confidence)
          → final report with full audit trail
```

### Article 14 — Human Oversight

| Requirement | Implementation |
|-------------|---------------|
| Design for human oversight | System produces reports for analyst review, not autonomous decisions |
| Ability to intervene | CLI and Streamlit UI allow analysts to inspect all intermediate outputs |
| Ability to override | YAML rules are editable without code changes; analysts can modify classification logic |
| Understanding of system capabilities | Disclaimer present on all trust/risk outputs |

### Article 15 — Accuracy, Robustness, Cybersecurity

| Requirement | Implementation |
|-------------|---------------|
| Appropriate levels of accuracy | Deterministic rule engine ensures reproducible classification; LLM outputs carry confidence scores |
| Robustness against errors | Mock mode with pre-computed fixtures for testing without API dependency; rate limiting prevents API failures |
| Resilience to adversarial inputs | Input text is hashed (SHA-256) for integrity; prompt injection risks mitigated by structured output schema |
| Cybersecurity | API keys via environment variables (not hardcoded); no user data stored beyond audit logs |

## Limitations and Disclosure

This mapping documents **design intent**, not a formal conformity
assessment. A production deployment would require:

1. Conformity assessment per Article 43
2. Registration in the EU database per Article 49
3. Designation of an authorized representative if deployed from
   outside the EU (Article 22)
4. Validation of classification accuracy on a labeled dataset
5. Formal serious incident reporting procedures (Article 73)

## References

- Regulation (EU) 2024/1689 — EU AI Act
- Regulation (EU) 2023/1114 — MiCAR
- Trerotola, Parente, Calvaresi (2026) — reference paper
