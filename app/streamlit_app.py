"""Streamlit UI for the MiCAR Compliance Agent."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mas.config import Settings  # noqa: E402
from mas.factory import create_pipeline  # noqa: E402
from mas.ingest.reader import read_document, read_text  # noqa: E402
from mas.report import to_json, to_markdown  # noqa: E402
from mas.schemas.report import ComplianceReport  # noqa: E402

EXAMPLES_DIR = Path(__file__).parent / "examples"


def _build_report(state: dict) -> ComplianceReport:  # type: ignore[type-arg]
    return ComplianceReport(
        input_hash=state["input_hash"],
        timestamp=datetime.fromisoformat(state.get("timestamp", datetime.now(UTC).isoformat())),
        prompt_version=state.get("prompt_version", "unknown"),
        model_id=state.get("model_id", "unknown"),
        asset_flags=state["asset_flags"],
        classification=state["classification"],
        compliance_flags=state["compliance_flags"],
    )


def main() -> None:
    st.set_page_config(
        page_title="MiCAR Compliance Agent",
        page_icon="🏛️",
        layout="wide",
    )

    st.title("MiCAR Compliance Agent")
    st.caption(
        "Hybrid neuro-symbolic analysis of crypto-asset whitepapers "
        "for EU MiCAR regulatory compliance"
    )

    # --- Sidebar ---
    with st.sidebar:
        st.header("Configuration")
        mock_mode = st.toggle("Mock Mode", value=True, help="Use pre-computed responses (no API key needed)")

        if not mock_mode:
            api_key = st.text_input("OpenAI API Key", type="password")
        else:
            api_key = ""

        st.divider()
        st.markdown(
            "**Paper:** Trerotola, Parente, Calvaresi (2026)  \n"
            "**Architecture:** LangGraph + YAML Rule Engine  \n"
            "[GitHub](https://github.com) | [SCOPE.md](SCOPE.md)"
        )

    # --- Input ---
    st.header("Input")

    tab_paste, tab_upload, tab_example = st.tabs(["Paste Text", "Upload File", "Examples"])

    whitepaper_text = None

    with tab_paste:
        pasted = st.text_area(
            "Paste whitepaper or website content:",
            height=300,
            placeholder="Paste the full text of a crypto-asset whitepaper here...",
        )
        if pasted.strip():
            whitepaper_text = pasted.strip()

    with tab_upload:
        uploaded = st.file_uploader(
            "Upload a whitepaper file",
            type=["txt", "md", "pdf"],
        )
        if uploaded is not None:
            if uploaded.name.endswith(".pdf"):
                st.warning("PDF support requires pymupdf. Install with: `uv pip install 'mas[ingest]'`")
                # Save to temp and read
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = Path(tmp.name)
                try:
                    whitepaper_text = read_document(tmp_path)
                except Exception as e:
                    st.error(f"Failed to read PDF: {e}")
            else:
                whitepaper_text = uploaded.read().decode("utf-8").strip()

    with tab_example:
        examples = sorted(EXAMPLES_DIR.glob("*.md")) if EXAMPLES_DIR.exists() else []
        if examples:
            example_names = {f.stem.replace("_", " ").title(): f for f in examples}
            selected = st.selectbox("Select an example:", list(example_names.keys()))
            if selected:
                example_path = example_names[selected]
                whitepaper_text = example_path.read_text()
                with st.expander("Preview"):
                    st.markdown(whitepaper_text[:500] + "...")
        else:
            st.info("No examples found. Add .md files to app/examples/")

    # --- Analyze ---
    st.divider()

    if st.button("Analyze", type="primary", disabled=whitepaper_text is None):
        if whitepaper_text is None:
            st.error("Please provide input text.")
            return

        settings = Settings()
        settings.mock_mode = mock_mode
        if not mock_mode and api_key:
            settings.openai_api_key = api_key

        try:
            pipeline = create_pipeline(settings)
        except Exception as e:
            st.error(f"Failed to create pipeline: {e}")
            return

        with st.spinner("Analyzing whitepaper..."):
            try:
                state = pipeline.invoke({"whitepaper_text": whitepaper_text})
                report = _build_report(state)
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                return

        # --- Results ---
        st.header("Results")

        cls = report.classification
        score = report.compliance_score

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Classification", cls.micar_class.value.upper())
        col2.metric("Compliance Score", f"{score:.0%}")
        col3.metric("Disclosures", f"{report.fulfilled_count}/{report.total_disclosures}")
        col4.metric("Model", report.model_id)

        # Classification details
        st.subheader("Classification")
        st.markdown(f"**Triggered Rules:** {', '.join(cls.triggered_rules)}")
        st.markdown(f"**Explanation:** {cls.explanation}")

        # Asset flags
        st.subheader("Asset Flags (Stage 1)")
        flag_data = []
        for name in type(report.asset_flags).model_fields:
            flag = getattr(report.asset_flags, name)
            flag_data.append({
                "Flag": name,
                "Value": "True" if flag.value else "False",
                "Confidence": f"{flag.confidence:.0%}",
                "Evidence": flag.evidence[:100],
            })
        st.dataframe(flag_data, use_container_width=True, hide_index=True)

        # Disclosure checklist
        st.subheader("Disclosure Checklist (Stage 3)")
        disc_data = []
        for d in report.compliance_flags.disclosures:
            disc_data.append({
                "Requirement": d.requirement_id,
                "Fulfilled": "Yes" if d.fulfilled else "No",
                "Confidence": f"{d.confidence:.0%}",
                "Evidence": d.evidence[:100],
            })
        st.dataframe(disc_data, use_container_width=True, hide_index=True)

        # Export
        st.subheader("Export")
        col_md, col_json = st.columns(2)
        with col_md:
            st.download_button(
                "Download Markdown Report",
                data=to_markdown(report),
                file_name="compliance_report.md",
                mime="text/markdown",
            )
        with col_json:
            st.download_button(
                "Download JSON Report",
                data=to_json(report),
                file_name="compliance_report.json",
                mime="application/json",
            )


if __name__ == "__main__":
    main()
