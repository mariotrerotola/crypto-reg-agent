# Piano dei requisiti — MVP Compliance Agent

## 1. Obiettivi del progetto

Il sistema e' una **reference implementation open-source** del Compliance Agent descritto nella Section 4.3 del paper Trerotola, Parente, Calvaresi (2026). L'obiettivo primario non e' replicare l'intero sistema MAS del paper, ma dimostrare in forma minimale, riproducibile e auditabile l'architettura hybrid neuro-symbolic che combina estrazione semantica LLM-based con un rule engine deterministico per la classificazione MiCAR e la verifica di disclosure.

Gli obiettivi secondari sono tre, in ordine di priorita'. Primo, fornire un artefatto tecnico difendibile in colloqui per ruoli Applied Scientist/ML Engineer in RegTech europei. Secondo, offrire alla community accademica una base di codice pulita che chiunque possa scaricare, eseguire localmente, e estendere per altre giurisdizioni. Terzo, produrre un documento di mapping EU AI Act che dimostri come un sistema di compliance regolamentare soddisfi gli Articoli 9-15 in pratica.

### Non-obiettivi

Il sistema **non** deve essere production-ready per un regolatore reale, **non** deve replicare i risultati numerici del paper sui 227k token, **non** deve sostituire il giudizio di un analista umano, **non** deve fornire consulenza legale, e **non** deve integrare le altre componenti del paper (Searcher, Crawler, On-Chain Agent, Reconciliator, frontend Next.js, MAS distribuito).

## 2. Stakeholder e utenti attesi

1. **Hiring manager tecnico** — apre il repo in 3-5 minuti per giudicare il profilo
2. **Ricercatore/studente** — clona il repo, esegue i test, legge il codice
3. **Compliance analyst** — apre la UI, carica un whitepaper, guarda l'output

## 3. Requisiti funzionali

### Must-have (MVP)

- Accettare whitepaper come testo, PDF, o Markdown
- Estrazione a due stadi (AssetFlags via LLM + classificazione deterministica)
- Prompt riprodotti letteralmente da Appendix C.1 e C.2
- Classificazione MiCAR da Tabella A1 come rule engine Python puro
- Verifica disclosure con ComplianceFlags
- Score di compliance (Eq. 2: fulfilled / applicable)
- Report strutturato con classe, flag, checklist, score, evidence
- Modalita' mock con output pre-computati da JSON
- Audit logging JSON con timestamp, prompt version, model version, input hash

### Should-have

- Flag weights configurabili via file
- CLI per batch processing
- 5-10 esempi pre-caricati nella UI
- Export report Markdown/JSON

### Won't-have in MVP

- Crawler, registri crypto, bytecode analysis, on-chain, multi-utente, database, REST API, WebSocket, MAS distribuito, giurisdizioni non-MiCAR

## 4. Requisiti non-funzionali

- **Riproducibilita'**: temperature bassa, seed fisso, prompt versionati
- **Auditabilita'**: ogni flag tracciabile a citazione testuale
- **Osservabilita'**: structured logging JSON (latenza, costo)
- **Portabilita'**: Python 3.12+, `uv pip install -e .`, Docker opzionale
- **Estensibilita'**: swap giurisdizione = 3 file (flags, rules, disclosures)
- **Qualita' codice**: coverage >70% su rule engine, ruff + mypy --strict, Pydantic v2, Conventional Commits
- **Documentazione**: README <5 min, architecture.md, paper_mapping.md, eu_ai_act_mapping.md, SCOPE.md

## 5. Vincoli

- Licenza MIT
- Paper citato nel README
- Prompt LLM riprodotti letteralmente dall'appendice
- No uso logo/nome CONSOB
- Dati esempio con licenza pubblica
- Ack co-autori prima di pubblicazione

## 6. Criteri di accettazione

- Tutti must-have implementati e testati
- README eseguibile <5 min in mock mode
- CI verde su main
- EU AI Act mapping scritto
- 5+ whitepaper esempio funzionanti
- Tag v1.0.0 con CHANGELOG

## 7. Rischi e mitigazioni

1. **Scope creep** → SCOPE.md + stratificazione must/should/won't
2. **Costo LLM** → mock mode + esempi pre-computati
3. **Drift fedelta' al paper** → paper_mapping.md + prompt letterali

## 8. Timeline

- Settimana 1: scheletro + rule engine → v0.1.0
- Settimana 2: Compliance Agent + LLM + logging → v0.2.0
- Settimana 3: UI Streamlit + CLI + esempi → v0.3.0
- Settimana 4: docs + polish + demo → v1.0.0
- Settimana 5 (overflow): tagliare should-have, non estendere tempo
