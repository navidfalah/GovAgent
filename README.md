# GovAgents — Multi-Agent AI Governance & Policy Reasoning System

> A multi-agent AI system for analyzing AI governance requirements, evaluating compliance and risk, and producing evidence-backed governance decisions.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-universal-purple.svg)](https://litellm.ai)

## Architecture

GovAgents uses **6 specialized agents** orchestrated through an async pipeline:

```
                 Proposal
                    │
             Orchestrator
                    │
    ┌───────────────┼───────────────┐
    │               │               │
  Policy          Risk           Technical
  Agent           Agent            Agent
    │               │               │
    └───────────────┼───────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
     Compliance             Ethics &
       Agent               Sovereignty
         │                     │
         └──────────┬──────────┘
                    │
           [Debate Protocol]
           (if disagreements)
                    │
            Governance Agent
                    │
            Final Report
```

Each agent has a distinct responsibility:

| Agent | Responsibility |
|---|---|
| **Policy Agent** | Searches policy corpus, identifies applicable requirements |
| **Risk Agent** | Identifies and scores technical, legal, ethical risks |
| **Technical Agent** | Analyzes architecture for governance compliance gaps |
| **Compliance Agent** | Checks whether the proposal satisfies each requirement |
| **Ethics & Sovereignty Agent** | Evaluates 7 ethical dimensions |
| **Governance Agent** | Synthesizes all outputs into a final decision |

## Quick Start

### 1. Clone and install

```bash
git clone <repo>
cd GovAgent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Run the server

```bash
uvicorn govagents.api.main:app --reload
```

The server auto-ingests the built-in policy corpus on first start.

### 4. Open the UI

Navigate to **http://localhost:8000** in your browser.

## CLI Demo

```bash
# Ingest policies manually
python scripts/ingest_policies.py

# Run a demo assessment
python scripts/run_demo.py
```

## API

```bash
# Submit assessment
curl -X POST http://localhost:8000/api/assess \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Employee Monitoring AI",
    "description": "An AI system that monitors employee communications...",
    "sector": "enterprise"
  }'

# Get assessment result
curl http://localhost:8000/api/assess/{id}

# Stream real-time updates (SSE)
curl http://localhost:8000/api/assess/{id}/stream

# Browse policy corpus
curl http://localhost:8000/api/policies

# API docs
open http://localhost:8000/api/docs
```

## Built-in Policy Corpus

| Policy | Type | Articles |
|---|---|---|
| EU AI Act (2024/1689) | Regulation | Art. 6, 9, 10, 11, 13, 14, 15, 26, 50, 99 |
| GDPR (2016/679) | Regulation | Art. 5, 6, 13, 22, 25, 35, 83 |
| OECD AI Principles | Framework | Principles 1.1–1.5 |
| NIST AI RMF | Framework | GOVERN, MAP, MEASURE, MANAGE |
| EU HLEG AI Guidelines | Guideline | Requirements 1–7 |

## Supported LLM Providers

Configure via `LLM_MODEL` and `LLM_PROVIDER` in `.env`:

| Provider | Model Example | Key Env Var |
|---|---|---|
| Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| Groq | `groq/llama-3.1-70b-versatile` | `GROQ_API_KEY` |
| Ollama | `ollama/llama3.1` | — |

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
govagents/
├── core/           # Config, LLM client, data models, logging
├── agents/         # 6 specialized governance agents
├── orchestration/  # Pipeline coordinator, message bus, debate protocol
├── policies/       # Document ingestion, parsing, ChromaDB retrieval
├── knowledge_graph/# NetworkX-based governance KG (Phase 4)
├── api/            # FastAPI app with SSE streaming
├── frontend/       # Rich SPA (HTML/CSS/JS)
scripts/            # CLI tools
tests/              # Unit & integration tests
configs/            # YAML configuration
```

## Assessment Output

```
Decision:             CONDITIONAL_APPROVAL
Overall Risk:         HIGH
Compliance Confidence: 52%
Uncertainty:          Moderate

Key Issues:
  1. Employee monitoring without adequate safeguards
  2. Transparency requirements not addressed
  3. No human oversight mechanism defined
  4. DPIA not conducted (GDPR Art. 35)

Required Actions:
  [P1] Conduct Data Protection Impact Assessment
  [P2] Define human oversight procedure
  [P3] Implement employee transparency mechanism
  [P4] Integrate explainability into AI pipeline

Evidence: EU AI Act Art. 13, 14 · GDPR Art. 22, 35 · OECD Principle 1.3
```