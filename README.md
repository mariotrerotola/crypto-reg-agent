# MiCAR Compliance Agent

A hybrid neuro-symbolic system for automated MiCAR (EU Markets in Crypto-Assets Regulation) compliance analysis of crypto-asset whitepapers.

Reference implementation of the Compliance Agent described in:

> Trerotola, M., Parente, M., & Calvaresi, D. (2026). *[Paper Title]*. [Venue].

## Architecture

The system implements a 3-stage analysis pipeline orchestrated via LangGraph:

1. **Asset Flag Extraction** (LLM) — Extracts boolean asset characteristics from whitepaper text using structured output
2. **MiCAR Classification** (Rule Engine) — Deterministic classification into MiCAR categories using YAML-driven rules
3. **Disclosure Verification** (LLM) — Verifies compliance with class-specific disclosure requirements

## Quickstart

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/new_mas.git
cd new_mas
uv sync --all-extras

# Run in mock mode (no API key needed)
MAS_MOCK_MODE=true uv run streamlit run app/streamlit_app.py

# Or with a real API key
cp .env.example .env  # Add your OPENAI_API_KEY
uv run streamlit run app/streamlit_app.py
```

## Project Status

This project is under active development. See [SCOPE.md](SCOPE.md) for explicit non-goals and boundaries.

## License

MIT
