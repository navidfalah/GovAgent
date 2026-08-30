# GovAgents: Multi-Agent AI Governance System

<div align="center">
  <p><strong>A modular, event-driven multi-agent system for reasoning about AI policy, risk, ethics, and compliance.</strong></p>
</div>

## Overview

**GovAgents** evaluates AI system proposals and technical architectures against a complex corpus of global policies (EU AI Act, GDPR, NIST RMF, OECD Principles) to produce evidence-backed governance decisions. 

Rather than relying on a single large language model (LLM) to perform all reasoning, GovAgents uses a **specialized multi-agent architecture** where agents focus on distinct aspects of governance (e.g., Risk, Ethics, Technical Architecture, Policy Compliance).

## Key Features

- 🤖 **6 Specialized Agents**: Dedicated agents for Policy Retrieval, Risk Assessment, Technical Review, Compliance, Ethics, and Governance Synthesis.
- 🧩 **Advanced Plugin Architecture**: Agents and Capabilities (tools) are dynamically loaded via a `@registry` system, making the system highly extensible.
- 📡 **Event-Driven Pub/Sub**: Inter-agent communication is handled by an asynchronous Message Bus supporting real-time Server-Sent Events (SSE).
- ⚖️ **Automated Agent Debate**: Disagreements between agents (e.g., the Technical Agent disagrees with the Risk Agent on a threat severity) are detected and resolved via an LLM debate protocol.
- 📚 **RAG Policy Corpus**: Built-in ingestion and semantic search (ChromaDB) over a complex YAML-based policy corpus.
- 🎨 **Premium Glassmorphism UI**: A stunning dark-mode Single Page Application (SPA) to visualize the real-time agent pipeline and governance reports.

---

## 🏗️ Architecture

GovAgents uses a dynamic, decoupled architecture heavily relying on Dependency Injection (DI) and a Plugin Registry.

```text
govagents/
├── core/           # DI Container, Plugin Registry, Shared Pydantic Models, LLM Client
├── capabilities/   # Reusable tools (VectorSearch, NLIChecker) injected into agents
├── agents/         # Auto-discovered Agents (Policy, Risk, Technical, Compliance, etc.)
├── orchestration/  # Async Coordinator, Debate Protocol, Event-Driven Message Bus
├── policies/       # YAML Corpus parser, ChromaDB ingestion, Semantic Retrieval
├── api/            # FastAPI routes & SSE streaming
└── frontend/       # Vanilla JS/CSS Glassmorphism Web App
```

### The Agent Pipeline
1. **Parallel Analysis**: The **Policy Agent** retrieves laws, the **Risk Agent** calculates threat vectors, and the **Technical Agent** reviews the architecture.
2. **Sequential Assessment**: The **Compliance Agent** and **Ethics Agent** evaluate the findings from Phase 1.
3. **Debate**: If the Orchestrator detects conflicting agent reasoning, it triggers the `DebateProtocol` to resolve it.
4. **Synthesis**: The **Governance Agent** reviews all outputs and makes a final `APPROVED`, `CONDITIONAL_APPROVAL`, `REJECTED`, or `ABSTAINED` decision.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- An API Key for Google Gemini (used via LiteLLM)

### Installation

1. **Clone the repository and set up a virtual environment:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies:**
```bash
pip install -e ".[dev]"
```

3. **Set up your environment variables:**
```bash
cp .env.example .env
# Open .env and add your GEMINI_API_KEY
```

### Quickstart

**1. Ingest the Policy Corpus**  
This parses the YAML policies (EU AI Act, GDPR, etc.) and creates local embeddings in ChromaDB.
```bash
python3 scripts/ingest_policies.py
```

**2. Start the FastAPI Server**
```bash
uvicorn govagents.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**3. Run an Assessment**  
Open your browser to `http://localhost:8000`. You can select an example proposal (e.g., "Employee monitoring") and watch the multi-agent pipeline stream its reasoning in real-time.

---

## 🛠️ Extending the System

GovAgents is designed to be easily extensible. 

### Adding a New Agent
Because of the Plugin Registry, you can add a new agent simply by subclassing `BaseAgent` and decorating it.

```python
from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import AgentRole

@registry.register_agent("SecurityAgent")
class SecurityAgent(BaseAgent):
    role = AgentRole.TECHNICAL
    description = "Focuses purely on cybersecurity threat modeling."
    
    async def run(self, context):
        # Implementation here
        pass
```

### Adding a New Capability (Tool)
Extract complex logic into capabilities that can be injected into any agent.

```python
from govagents.capabilities.base import Capability
from govagents.core.registry import registry

@registry.register_capability("WebSearch")
class WebSearchCapability(Capability):
    async def execute(self, query: str):
        # Perform search and return results
        return results
```

---

## 🧪 Testing

GovAgents includes a comprehensive `pytest` suite.
```bash
python3 -m pytest tests/ -v
```

## 📝 License
MIT License