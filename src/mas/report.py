"""Report export utilities (Markdown and JSON)."""

from __future__ import annotations

from mas.schemas.report import ComplianceReport


def to_json(report: ComplianceReport, indent: int = 2) -> str:
    """Serialize a ComplianceReport to JSON."""
    return report.model_dump_json(indent=indent)


def to_markdown(report: ComplianceReport) -> str:
    """Render a ComplianceReport as a human-readable Markdown document."""
    lines: list[str] = []
    cls = report.classification
    flags = report.asset_flags
    comp = report.compliance_flags

    lines.append("# MiCAR Compliance Report")
    lines.append("")
    lines.append(f"**Classification:** `{cls.micar_class.value.upper()}`")
    lines.append(
        f"**Compliance Score:** {report.compliance_score:.1%} "
        f"({report.fulfilled_count}/{report.total_disclosures})"
    )
    lines.append(f"**Model:** {report.model_id}")
    lines.append(f"**Prompt Version:** {report.prompt_version}")
    lines.append(f"**Input Hash:** `{report.input_hash[:16]}...`")
    lines.append(f"**Timestamp:** {report.timestamp.isoformat()}")
    lines.append("")

    # Classification reasoning
    lines.append("## Classification")
    lines.append("")
    lines.append(f"**Triggered Rules:** {', '.join(cls.triggered_rules)}")
    lines.append(f"**Explanation:** {cls.explanation}")
    lines.append("")

    # Asset flags
    lines.append("## Asset Flags")
    lines.append("")
    lines.append("| Flag | Value | Confidence | Evidence |")
    lines.append("|------|-------|------------|----------|")
    for name in type(flags).model_fields:
        flag = getattr(flags, name)
        icon = "True" if flag.value else "False"
        evidence_short = flag.evidence[:80] + "..." if len(flag.evidence) > 80 else flag.evidence
        lines.append(f"| `{name}` | {icon} | {flag.confidence:.0%} | {evidence_short} |")
    lines.append("")

    # Disclosure checklist
    lines.append("## Disclosure Checklist")
    lines.append("")
    lines.append(f"**Asset Class:** `{comp.micar_class}`")
    lines.append("")
    lines.append("| Requirement | Fulfilled | Confidence | Evidence |")
    lines.append("|-------------|-----------|------------|----------|")
    for d in comp.disclosures:
        icon = "Yes" if d.fulfilled else "No"
        evidence_short = d.evidence[:80] + "..." if len(d.evidence) > 80 else d.evidence
        lines.append(f"| `{d.requirement_id}` | {icon} | {d.confidence:.0%} | {evidence_short} |")
    lines.append("")

    # Trust & Risk Indicators
    if report.trust_analysis:
        trust = report.trust_analysis
        lines.append("## Trust & Risk Indicators")
        lines.append("")
        lines.append(f"> {trust.disclaimer}")
        lines.append("")
        rl = trust.risk_level.value.upper().replace("_", " ")
        lines.append(f"**Trust Score:** {trust.overall_score:.0f}%")
        lines.append(f"**Risk Level:** `{rl}`")
        lines.append("")
        lines.append("| Signal | Score (1-5) | Confidence | Evidence |")
        lines.append("|--------|-------------|------------|----------|")
        for name in type(trust.signals).model_fields:
            signal = getattr(trust.signals, name)
            ev = signal.evidence[:80] + "..." if len(signal.evidence) > 80 else signal.evidence
            lines.append(f"| `{name}` | {signal.score}/5 | {signal.confidence:.0%} | {ev} |")
        if trust.contract_modifier != 0:
            lines.append(f"**On-Chain Modifier:** `{trust.contract_modifier:+.0f}`")
        lines.append("")

    # On-Chain Security (GoPlus)
    if report.contract_security:
        sec = report.contract_security
        lines.append("## On-Chain Security (GoPlus)")
        lines.append("")
        lines.append(f"**Chain:** `{sec.chain}` | **Holders:** {sec.holder_count}")
        lines.append("")
        checks = [
            ("Honeypot", sec.is_honeypot, True),
            ("Open Source", sec.is_open_source, False),
            ("Proxy/Upgradeable", sec.is_proxy, True),
            ("Mintable", sec.is_mintable, True),
            ("Hidden Owner", sec.hidden_owner, True),
            ("Can Reclaim Ownership", sec.can_take_back_ownership, True),
            ("Owner Can Modify Balance", sec.owner_change_balance, True),
            ("Transfer Pausable", sec.transfer_pausable, True),
            ("Blacklist", sec.is_blacklisted, True),
            ("Self-Destruct", sec.selfdestruct, True),
        ]
        lines.append("| Check | Status |")
        lines.append("|-------|--------|")
        for label, value, is_danger in checks:
            icon = ("FAIL" if value else "OK") if is_danger else ("OK" if value else "FAIL")
            lines.append(f"| {label} | {icon} |")
        if sec.buy_tax > 0 or sec.sell_tax > 0:
            lines.append(f"| Buy Tax | {sec.buy_tax:.1f}% |")
            lines.append(f"| Sell Tax | {sec.sell_tax:.1f}% |")
        if sec.trust_list:
            lines.append("| GoPlus Trust List | YES |")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by MiCAR Compliance Agent*")

    return "\n".join(lines)
