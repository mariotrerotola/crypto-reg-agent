"""Generic YAML-driven rule interpreter for deterministic classification.

The engine loads rule definitions and disclosure checklists from YAML files
and evaluates them against a dictionary of boolean flags. No LLM is involved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mas.schemas.classification import ClassificationResult, MiCARClass


class RuleEngineError(Exception):
    """Raised when rule evaluation encounters an invalid state."""


class RuleEngine:
    """YAML-driven rule interpreter.

    Loads classification rules and disclosure checklists from a jurisdiction
    directory. Rules are evaluated top-to-bottom with first-match-wins
    semantics.

    Args:
        rules_dir: Path to a jurisdiction directory containing
            ``classification.yaml`` and ``disclosures.yaml``.
    """

    def __init__(self, rules_dir: Path) -> None:
        self._rules_dir = rules_dir
        self._classification = self._load_yaml("classification.yaml")
        self._disclosures = self._load_yaml("disclosures.yaml")

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        path = self._rules_dir / filename
        if not path.exists():
            msg = f"Rule file not found: {path}"
            raise FileNotFoundError(msg)
        with path.open() as f:
            data: dict[str, Any] = yaml.safe_load(f)
        return data

    def classify(self, flags: dict[str, bool]) -> ClassificationResult:
        """Evaluate classification rules against extracted flags.

        Rules are evaluated in order. The first rule whose conditions match
        determines the classification. An empty conditions block always matches
        (used for fallback rules).

        Supports both MiCAR and non-MiCAR jurisdictions.  For non-MiCAR rule
        sets, the result string is mapped to the closest ``MiCARClass`` enum
        value and the original label is stored in ``jurisdiction_class``.

        Args:
            flags: Mapping of flag names to boolean values.

        Returns:
            A ClassificationResult with the matched class, rule IDs, and explanation.
        """
        rules: list[dict[str, Any]] = self._classification["rules"]
        jurisdiction = self.jurisdiction

        for rule in rules:
            conditions: dict[str, Any] = rule.get("conditions", {})
            if self._evaluate_conditions(conditions, flags):
                result_str = rule["result"]
                micar_class = self._to_micar_class(result_str)
                return ClassificationResult(
                    micar_class=micar_class,
                    triggered_rules=[rule["id"]],
                    explanation=f"Rule {rule['id']}: {rule.get('description', '')}",
                    jurisdiction=jurisdiction,
                    jurisdiction_class=result_str,
                )

        return ClassificationResult(
            micar_class=MiCARClass.OTHER,
            triggered_rules=[],
            explanation="No rules matched; defaulting to OTHER.",
            jurisdiction=jurisdiction,
            jurisdiction_class="other",
        )

    @staticmethod
    def _to_micar_class(result: str) -> MiCARClass:
        """Map a rule result string to a MiCARClass enum value.

        Exact matches use the enum directly.  Non-MiCAR values are mapped
        to ``SECURITY`` (for securities-like classes) or ``OTHER``.
        """
        try:
            return MiCARClass(result)
        except ValueError:
            # Non-MiCAR jurisdiction: map to closest MiCAR class
            security_like = {"security", "investment_contract", "note", "equity", "debt"}
            non_micar_like = {"non_security_nft", "commodity"}
            if result.lower() in security_like:
                return MiCARClass.SECURITY
            if result.lower() in non_micar_like:
                return MiCARClass.NON_MICAR
            return MiCARClass.OTHER

    def get_disclosure_checklist(self, micar_class: str) -> list[dict[str, str]]:
        """Return the applicable disclosure items for a MiCAR class.

        Args:
            micar_class: One of the MiCARClass string values.

        Returns:
            List of dicts with ``id`` and ``description`` keys.

        Raises:
            RuleEngineError: If no checklist is defined for the given class.
        """
        checklists: dict[str, list[dict[str, str]]] = self._disclosures["checklists"]
        if micar_class not in checklists:
            msg = f"No disclosure checklist for class: {micar_class}"
            raise RuleEngineError(msg)
        return checklists[micar_class]

    @property
    def jurisdiction(self) -> str:
        """Return the jurisdiction identifier from the classification rules."""
        return str(self._classification.get("jurisdiction", "unknown"))

    @property
    def version(self) -> str:
        """Return the version of the classification rules."""
        return str(self._classification.get("version", "unknown"))

    def _evaluate_conditions(self, conditions: dict[str, Any], flags: dict[str, bool]) -> bool:
        """Evaluate a conditions block with 'all', 'any', 'none' logic.

        An empty conditions dict always matches (fallback rule).
        """
        if not conditions:
            return True

        # 'all' — every condition must match
        if "all" in conditions:
            for cond in conditions["all"]:
                flag_name = cond["flag"]
                expected = cond["equals"]
                if flags.get(flag_name) != expected:
                    return False

        # 'any' — at least one condition must match
        if "any" in conditions:
            any_matched = False
            for cond in conditions["any"]:
                flag_name = cond["flag"]
                expected = cond["equals"]
                if flags.get(flag_name) == expected:
                    any_matched = True
                    break
            if not any_matched:
                return False

        # 'none' — no condition may match (exclusion)
        if "none" in conditions:
            for cond in conditions["none"]:
                flag_name = cond["flag"]
                expected = cond["equals"]
                if flags.get(flag_name) == expected:
                    return False

        return True
