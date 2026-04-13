"""CLI entry point for the MiCAR Compliance Agent."""

from __future__ import annotations

import sys

try:
    import typer
except ImportError:
    print("CLI requires typer. Install with: uv pip install 'mas[cli]'")  # noqa: T201
    sys.exit(1)

import logging
from pathlib import Path
from typing import Any

from mas.config import Settings  # noqa: E402
from mas.factory import create_pipeline  # noqa: E402
from mas.ingest.reader import read_document  # noqa: E402
from mas.report import to_json, to_markdown  # noqa: E402
from mas.schemas.report import ComplianceReport  # noqa: E402

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="mas",
    help="MiCAR Compliance Agent — Analyze crypto-asset whitepapers.",
    no_args_is_help=True,
)


def _build_report(state: dict) -> ComplianceReport:  # type: ignore[type-arg]
    """Assemble a ComplianceReport from pipeline state."""
    from datetime import UTC, datetime

    return ComplianceReport(
        input_hash=state["input_hash"],
        timestamp=datetime.fromisoformat(state.get("timestamp", datetime.now(UTC).isoformat())),
        prompt_version=state.get("prompt_version", "unknown"),
        model_id=state.get("model_id", "unknown"),
        asset_flags=state["asset_flags"],
        classification=state["classification"],
        compliance_flags=state["compliance_flags"],
        trust_analysis=state.get("trust_analysis"),
        contract_security=state.get("contract_security"),
    )


@app.command()
def analyze(  # noqa: B008
    file: Path = typer.Argument(..., help="Path to whitepaper file (.txt, .md, .pdf)"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, json"
    ),
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Write output to file"),
    mock: bool = typer.Option(False, "--mock", help="Use mock mode (no API key needed)"),
) -> None:
    """Analyze a single whitepaper for MiCAR compliance."""
    settings = Settings()
    if mock:
        settings.mock_mode = True

    text = read_document(file)
    pipeline = create_pipeline(settings)

    typer.echo(f"Analyzing: {file.name} ({len(text)} chars)...")
    state = pipeline.invoke({"whitepaper_text": text})

    report = _build_report(state)
    cls = report.classification.micar_class.value.upper()
    score = report.compliance_score
    fc = report.fulfilled_count
    td = report.total_disclosures

    typer.echo(f"Classification: {cls}")
    typer.echo(f"Compliance Score: {score:.1%} ({fc}/{td})")
    rules = ", ".join(report.classification.triggered_rules)
    typer.echo(f"Triggered Rules: {rules}")

    if report.trust_analysis:
        trust = report.trust_analysis
        rl = trust.risk_level.value.upper().replace("_", " ")
        typer.echo(f"Trust Score: {trust.overall_score:.0f}% ({rl})")

    content = to_json(report) if output_format == "json" else to_markdown(report)

    if output_file:
        output_file.write_text(content)
        typer.echo(f"Report written to: {output_file}")
    else:
        typer.echo("")
        typer.echo(content)


@app.command()
def batch(  # noqa: B008
    directory: Path = typer.Argument(..., help="Directory containing whitepaper files"),
    output_dir: Path = typer.Option("reports", "--output-dir", "-o", help="Output directory"),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format: markdown, json"
    ),
    mock: bool = typer.Option(False, "--mock", help="Use mock mode"),
) -> None:
    """Analyze all whitepapers in a directory."""
    settings = Settings()
    if mock:
        settings.mock_mode = True

    globs = ["*.md", "*.txt", "*.pdf"]
    files = [f for g in globs for f in directory.glob(g)]
    if not files:
        typer.echo(f"No supported files found in {directory}")
        raise typer.Exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = create_pipeline(settings)

    for f in sorted(files):
        typer.echo(f"Analyzing: {f.name}...")
        try:
            text = read_document(f)
            state = pipeline.invoke({"whitepaper_text": text})
            report = _build_report(state)

            ext = ".json" if output_format == "json" else ".md"
            out = output_dir / f"{f.stem}_report{ext}"
            content = to_json(report) if output_format == "json" else to_markdown(report)
            out.write_text(content)

            cls = report.classification.micar_class.value.upper()
            typer.echo(f"  -> {cls} (score: {report.compliance_score:.1%}) -> {out}")
        except Exception as e:
            typer.echo(f"  -> ERROR: {e}", err=True)

    typer.echo(f"Done. {len(files)} files processed.")


@app.command()
def search(  # noqa: B008
    query: str = typer.Argument(..., help="Project name or symbol (e.g. 'tether', 'UNI')"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, json"
    ),
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Write output to file"),
) -> None:
    """Search for a crypto project and analyze it for MiCAR compliance.

    Uses CoinGecko to discover the project, crawls its website, and runs
    the full 5-stage compliance analysis pipeline.
    """
    settings = Settings()
    pipeline = create_pipeline(settings, enable_search=True)

    typer.echo(f"Searching for: {query}...")
    state = pipeline.invoke({"project_query": query})

    report = _build_report(state)
    metadata = state.get("project_metadata")
    cls = report.classification.micar_class.value.upper()
    fc = report.fulfilled_count
    td = report.total_disclosures

    if metadata:
        typer.echo(f"Project: {metadata.name} ({metadata.symbol})")
        if metadata.categories:
            typer.echo(f"Categories: {', '.join(metadata.categories)}")
    typer.echo(f"Classification: {cls}")
    typer.echo(f"Compliance Score: {report.compliance_score:.1%} ({fc}/{td})")
    rules = ", ".join(report.classification.triggered_rules)
    typer.echo(f"Triggered Rules: {rules}")

    if report.trust_analysis:
        trust = report.trust_analysis
        rl = trust.risk_level.value.upper().replace("_", " ")
        typer.echo(f"Trust Score: {trust.overall_score:.0f}% ({rl})")

    content = to_json(report) if output_format == "json" else to_markdown(report)

    if output_file:
        output_file.write_text(content)
        typer.echo(f"Report written to: {output_file}")
    else:
        typer.echo("")
        typer.echo(content)


@app.command("scan-new")
def scan_new(  # noqa: B008
    limit: int = typer.Option(10, "--limit", "-n", help="Max new tokens to scan"),
    output_dir: Path = typer.Option(
        "reports/scan", "--output-dir", "-o", help="Output directory for reports"
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format: markdown, json"
    ),
) -> None:
    """Scan recently launched tokens for compliance and trust risks.

    Fetches newly created DEX pools from GeckoTerminal, runs GoPlus
    on-chain security checks, crawls websites, and runs the full
    compliance + trust analysis pipeline on each token.
    Results are sorted by risk level (highest risk first).
    """
    from mas.agents.crawler import WebCrawler
    from mas.agents.geckoterminal import GeckoTerminalClient, GeckoTerminalError
    from mas.agents.goplus import GoPlusClient

    settings = Settings()

    typer.echo(f"Fetching up to {limit} recently launched tokens from GeckoTerminal...")

    gt = GeckoTerminalClient(timeout=settings.crawler_timeout)
    try:
        new_tokens = gt.list_new_tokens(limit=limit)
    except GeckoTerminalError as e:
        typer.echo(f"Failed to fetch new tokens: {e}", err=True)
        raise typer.Exit(1) from None

    if not new_tokens:
        typer.echo("No new tokens found.")
        raise typer.Exit(0)

    typer.echo(f"Found {len(new_tokens)} tokens. Running analysis pipeline...")

    crawler = WebCrawler(timeout=settings.crawler_timeout, max_urls=2)
    goplus = GoPlusClient(timeout=settings.crawler_timeout)
    pipeline = create_pipeline(settings, enable_search=False)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: list[dict[str, str]] = []

    for i, meta in enumerate(new_tokens, 1):
        typer.echo(f"  [{i}/{len(new_tokens)}] {meta.name} ({meta.symbol})...")
        try:
            # GoPlus on-chain check
            goplus_mod = ""
            contract_sec = None
            for chain, addr in meta.contract_addresses.items():
                contract_sec = goplus.check_token(chain, addr)
                if contract_sec:
                    mod = contract_sec.trust_modifier()
                    flags = []
                    if contract_sec.is_honeypot:
                        flags.append("HONEYPOT")
                    if contract_sec.hidden_owner:
                        flags.append("hidden_owner")
                    if contract_sec.owner_change_balance:
                        flags.append("owner_mint")
                    if not contract_sec.is_open_source:
                        flags.append("closed_src")
                    if contract_sec.sell_tax > 0:
                        flags.append(f"tax={contract_sec.sell_tax:.0f}%")
                    goplus_mod = f"GoPlus:{mod:+.0f}"
                    if flags:
                        goplus_mod += f" [{','.join(flags)}]"
                    break

            # Crawl website
            urls = list(meta.website_urls)
            import contextlib

            text = None
            if urls:
                with contextlib.suppress(Exception):
                    text = crawler.crawl(urls)
            if not text or len(text) < 50:
                text = meta.description or f"Project: {meta.name} ({meta.symbol})"

            # Inject contract_security into state for trust modifier
            input_state: dict[str, Any] = {"whitepaper_text": text}
            if contract_sec:
                input_state["contract_security"] = contract_sec

            state = pipeline.invoke(input_state)
            report = _build_report(state)

            # Save report
            slug = meta.name.lower().replace(" ", "_")[:30]
            ext = ".json" if output_format == "json" else ".md"
            out = output_dir / f"{slug}_report{ext}"
            content = to_json(report) if output_format == "json" else to_markdown(report)
            out.write_text(content)

            cls = report.classification.micar_class.value.upper()
            comp_score = report.compliance_score
            trust = report.trust_analysis
            trust_str = f"{trust.overall_score:.0f}%" if trust else "N/A"
            risk = trust.risk_level.value if trust else "unknown"

            summary.append({
                "name": meta.name,
                "symbol": meta.symbol,
                "class": cls,
                "compliance": f"{comp_score:.0%}",
                "trust": trust_str,
                "risk": risk,
                "goplus": goplus_mod,
            })

            line = f"       {cls} | Trust: {trust_str}"
            if goplus_mod:
                line += f" | {goplus_mod}"
            typer.echo(line)

        except Exception as e:
            import traceback

            typer.echo(f"       ERROR: {e}", err=True)
            logger.debug("scan-new error for %s:\n%s", meta.name, traceback.format_exc())
            summary.append({
                "name": meta.name,
                "symbol": meta.symbol,
                "class": "ERROR",
                "compliance": "-",
                "trust": "-",
                "risk": "error",
                "goplus": "",
            })

    # Print sorted summary (highest risk first)
    risk_order = {
        "high_risk": 0, "elevated": 1, "moderate": 2,
        "low_risk": 3, "unknown": 4, "error": 5,
    }
    summary.sort(key=lambda x: risk_order.get(x["risk"], 99))

    typer.echo("")
    typer.echo(f"=== Scan Summary ({len(summary)} tokens) ===")
    typer.echo("")
    for s in summary:
        rl = s["risk"].upper().replace("_", " ")
        gp = f"  {s['goplus']}" if s.get("goplus") else ""
        typer.echo(
            f"  {rl:12s} {s['name']:30s} ({s['symbol']:6s}) "
            f"Trust: {s['trust']:>4s}  Class: {s['class']}{gp}"
        )

    typer.echo("")
    typer.echo(f"Reports saved to: {output_dir}/")
    gt.close()
    goplus.close()


if __name__ == "__main__":
    app()
