"""CLI entry point for the MiCAR Compliance Agent."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import typer
except ImportError:
    print("CLI requires typer. Install with: uv pip install 'mas[cli]'")  # noqa: T201
    sys.exit(1)

from mas.config import Settings
from mas.factory import create_pipeline
from mas.ingest.reader import read_document
from mas.report import to_json, to_markdown
from mas.schemas.report import ComplianceReport

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

    content = to_json(report) if output_format == "json" else to_markdown(report)

    if output_file:
        output_file.write_text(content)
        typer.echo(f"Report written to: {output_file}")
    else:
        typer.echo("")
        typer.echo(content)


if __name__ == "__main__":
    app()
