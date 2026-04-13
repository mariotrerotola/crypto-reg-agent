# Extending to New Jurisdictions

The MiCAR Compliance Agent was designed from the start to support
multiple regulatory jurisdictions.  The rule engine is completely
decoupled from any specific regulation — it evaluates YAML rule files
against a common set of asset flags.  Adding a new jurisdiction
requires **zero code changes**: you create a new directory with two
YAML files and point the engine at it.

This document walks through the included **US-SEC extension** as a
concrete example.

## Architecture: How It Works

```
src/mas/rules/
  micar_v1/              ← EU MiCAR (default)
    classification.yaml
    disclosures.yaml
  sec_v1/                ← US SEC (extension)
    classification.yaml
    disclosures.yaml
  fca_v1/                ← UK FCA (you could add this)
    ...
```

The `RuleEngine` class is jurisdiction-agnostic:

```python
from mas.rules.engine import RuleEngine

# EU MiCAR
eu_engine = RuleEngine(rules_dir=Path("src/mas/rules/micar_v1"))
eu_result = eu_engine.classify(flags)
# → jurisdiction="EU-MiCAR", jurisdiction_class="emt"

# US SEC
sec_engine = RuleEngine(rules_dir=Path("src/mas/rules/sec_v1"))
sec_result = sec_engine.classify(flags)
# → jurisdiction="US-SEC", jurisdiction_class="investment_contract"
```

Same engine class, same flag schema, same evaluation logic — different
rules, different taxonomy.

## Step-by-Step: Adding a New Jurisdiction

### Step 1: Create the Rules Directory

```bash
mkdir -p src/mas/rules/your_jurisdiction_v1/
```

### Step 2: Write `classification.yaml`

The classification file defines the taxonomy and the rules that map
asset flags to categories.

```yaml
version: "1.0"
jurisdiction: "YOUR-JURISDICTION"
description: "Classification rules for Your Regulation."

rules:
  - id: "RULE_1"
    description: "What this rule detects"
    conditions:
      all:                    # AND — every condition must match
        - flag: "flag_name"
          equals: true
      any:                    # OR — at least one must match
        - flag: "flag_a"
          equals: true
        - flag: "flag_b"
          equals: true
      none:                   # NOR — none may match (exclusion)
        - flag: "flag_c"
          equals: true
    result: "your_category"   # The classification label

  - id: "FALLBACK"
    description: "No indicators detected"
    conditions: {}            # Empty = always matches (fallback)
    result: "non_classifiable"
```

**Rules are evaluated top-to-bottom, first match wins.**

### Step 3: Write `disclosures.yaml`

The disclosure file defines what documentation is required for each
classification category.

```yaml
version: "1.0"
jurisdiction: "YOUR-JURISDICTION"

checklists:
  your_category:
    - id: "disclosure_1"
      article: "Section 5(a)"
      description: "What must be disclosed and why."
    - id: "disclosure_2"
      article: "Section 10(b)"
      description: "Another requirement."

  non_classifiable:
    - id: "insufficient_data"
      article: "N/A"
      description: "Insufficient information for classification."
```

### Step 4: Use It

```python
from mas.rules.engine import RuleEngine
from pathlib import Path

engine = RuleEngine(rules_dir=Path("src/mas/rules/your_jurisdiction_v1"))
result = engine.classify(flags)

print(result.jurisdiction)        # "YOUR-JURISDICTION"
print(result.jurisdiction_class)  # "your_category"
print(result.triggered_rules)     # ["RULE_1"]

# Get the applicable disclosure checklist
checklist = engine.get_disclosure_checklist("your_category")
```

### Step 5: Add Tests

```python
# tests/test_your_jurisdiction.py
from mas.rules.engine import RuleEngine
from tests.conftest import make_flags

engine = RuleEngine(rules_dir=Path("src/mas/rules/your_jurisdiction_v1"))

def test_your_rule():
    flags = make_flags(flag_name=True)
    result = engine.classify(flags)
    assert result.jurisdiction_class == "your_category"
```

## Included Example: US SEC (Howey Test)

The `sec_v1/` directory demonstrates this extensibility with a
simplified SEC rule set based on the **Howey Test** and the
**Securities Act of 1933**.

### SEC Classification Rules (7 rules)

| Rule | Legal Basis | Result |
|------|------------|--------|
| `HOWEY_FULL` | Howey Test: transferable + investment promise + reserves, no governance (FinHub decentralization factor) | `investment_contract` |
| `HOWEY_MARKETING` | SEC v. Telegram pattern: security language + investment promise + dividends | `investment_contract` |
| `SEC_EQUITY` | Securities Act § 2(a)(1): represents equity or has capital rights | `security` |
| `SEC_DEBT` | Securities Act § 2(a)(1): represents debt (note, bond) | `security` |
| `SEC_EXPLICIT` | Explicitly regulated as a security | `security` |
| `COMMODITY_UTILITY` | FinHub Framework: utility/governance without investment characteristics (CFTC jurisdiction) | `commodity` |
| `NFT_EXEMPT` | Unique NFT without investment promise | `non_security_nft` |

### SEC Disclosure Requirements

| Category | Requirements | Key Articles |
|----------|-------------|-------------|
| `investment_contract` | 9 items | Securities Act §5, §10, Reg S-K/S-X, FinHub Framework |
| `security` | 5 items | Securities Act §5, §10, Reg S-K |
| `commodity` | 3 items | Best practices, FinHub Framework |
| `non_security_nft` | 2 items | Howey Test, SEC informal guidance |

Key SEC-specific disclosure items not present in MiCAR:
- **`registration_or_exemption`** — Reg D / Reg A+ / Reg S exemption framework
- **`decentralization_status`** — per FinHub and Hinman Speech (2018)
- **`technology_description`** — per FinHub Framework (2019)
- **`no_investment_marketing`** — commodity tokens must not be marketed as investments

### Cross-Jurisdiction Comparison

The same asset flags produce different results under different
jurisdictions:

```python
flags = make_flags(utility_function=True, governance_function=True)

eu = micar_engine.classify(flags)
# → jurisdiction="EU-MiCAR", class="other" (utility token)

us = sec_engine.classify(flags)
# → jurisdiction="US-SEC", class="commodity" (potential CFTC jurisdiction)
```

This is tested in `tests/test_sec_rules.py::TestCrossJurisdiction`.

## Available Asset Flags

All jurisdictions share the same 19 boolean asset flags extracted by
the LLM in Stage 1.  These flags are jurisdiction-neutral — they
describe asset characteristics, not regulatory categories:

| Flag | Description |
|------|-------------|
| `regulated_as_security` | Classified under securities frameworks |
| `represents_equity` | Ownership or profit share rights |
| `represents_debt` | Financial obligation of issuer |
| `has_capital_rights` | Claims to dividends or liquidation |
| `investment_promise` | Marketed with promise of returns |
| `dividend_like` | Returns similar to dividends |
| `security_language` | Uses terms like "shares", "equity" |
| `rights_transferable` | Can be freely transferred/traded |
| `redeemable_in_fiat` | Convertible to fiat currency |
| `daily_redeemability` | Can be redeemed daily |
| `reserve_assets_held` | Issuer holds backing reserves |
| `audited_reserves` | Reserves independently audited |
| `redemption_policy_clear` | Clear redemption process |
| `backed_by_assets` | Backed by asset basket |
| `utility_function` | Provides access to services |
| `governance_function` | Confers voting rights |
| `nft_unique` | Unique non-fungible token |
| `whitepaper_present` | Formal documentation exists |
| `disclaimers_regulatory` | Regulatory disclaimers included |

## Potential Jurisdictions to Add

| Jurisdiction | Regulation | Effort |
|-------------|-----------|--------|
| UK FCA | Financial Services and Markets Act 2000 | Medium |
| Singapore MAS | Payment Services Act 2019 | Medium |
| Japan FSA | Payment Services Act / FIEA | Medium |
| Switzerland FINMA | DLT Act 2021 | Low |
| Dubai VARA | Virtual Assets Regulatory Authority | Low |
