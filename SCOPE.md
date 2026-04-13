# Scope — What This Project Is and Is Not

## In Scope (MVP)

- Single-agent compliance analysis of crypto-asset whitepapers against MiCAR
- 3-stage pipeline: LLM flag extraction → deterministic classification → LLM disclosure verification
- Streamlit UI for interactive analysis
- CLI for batch processing
- Mock mode for demo without API key
- Audit logging compliant with EU AI Act Art. 12

## Explicitly Out of Scope

The following are **not goals** of this project and will not be implemented:

- **Production readiness** — This is a reference implementation, not a regulatory tool
- **Multi-agent system** — No Searcher, Crawler, On-Chain Agent, or Reconciliator
- **Legal advice** — Outputs are informational, not legal counsel
- **Web crawling** — No automated whitepaper discovery or scraping
- **On-chain analysis** — No smart contract bytecode or blockchain data analysis
- **Multi-user/auth** — Single-user, no authentication or authorization
- **Database persistence** — File-based logging only, no RDBMS
- **REST API** — No HTTP API server (use CLI for programmatic access)
- **Real-time updates** — No WebSocket or streaming UI updates
- **Distributed MAS** — No message broker, no inter-agent communication
- **Non-MiCAR jurisdictions** — Architecture supports extension, but only MiCAR is implemented
- **Numerical replication** — Not targeting the paper's 227k token benchmark results
- **CoinMarketCap/registry integration** — No external crypto data sources

## Extension Points

The architecture is designed so that a future contributor can add a new jurisdiction by replacing three files:

1. `src/mas/rules/<jurisdiction>/classification.yaml`
2. `src/mas/rules/<jurisdiction>/disclosures.yaml`
3. `src/mas/prompts/<version>/*.md`

This is a design requirement, not a feature of the MVP.
