# AI-Agentic Workflow System (LangGraph + Smart Orchestrator)

A production-grade, event-driven multi-agent system designed for **dynamic workflow orchestration**, **cost optimization**, and **configurable safety policies**.

## 🚀 Key Features

- **Smart Orchestrator**: Uses LLMs to analyze user intent and dynamically generate execution plans (DAGs) instead of hardcoded state machines.
- **Agent Registry**: Centralized JSON definition (`langgraph_agents/agent_registry.json`) of agent capabilities, costs, and dependencies.
- **TOON Optimization**: Custom "Token-Oriented Object Notation" (`utils/toon_converter.py`) reduces LLM payload size by 20-40% for cost efficiency.
- **Policy-Driven**: Externalized business logic and safety rules in `policies/` (e.g., SLAs, forbidden topics).
- **Event-Based Architecture**: Decoupled agents communicate via a central `EventBus` and shared `StateStore`.

## 📂 Project Structure

```text
langgraph_workflow/
├── collab_agents/           # Concrete Agent Implementations (Logic)
│   ├── ingestion_agent.py   # Input normalization & validation
│   ├── intent_agent.py      # Intent detection & SLA routing
│   ├── planner_agent.py     # Execution strategy formulation
│   └── ... (memory, reasoning, etc.)
│
├── langgraph_agents/        # Core System Components
│   ├── smart_orchestrator.py # Main engine using LLM for planning
│   ├── agent_registry.json   # Metadata for all available agents
│   └── langgraph_system.py   # Base classes (EventBus, BaseAgent)
│
├── policies/                # Configuration Rules
│   ├── safety_policy.json    # Guardrails & compliance
│   └── intent_config.json    # SLA & routing definitions
│
├── utils/                   # Shared Utilities
│   ├── toon_converter.py     # JSON <-> TOON compression
│   └── CommonLogger.py       # Centralized JSONL logging
│
├── run_workflow.ps1         # Main execution entry point
├── architecture.md          # Detailed architectural documentation
└── requirements.txt         # Python dependencies
```

## 🛠️ Setup & Installation

1.  **Prerequisites**: Python 3.10+
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Environment**: Ensure your `config.py` is set up with necessary LLM API keys (Mistral/OpenAI).

## ▶️ Usage

### Interactive Mode
Run the script without arguments to enter an interactive session:
```powershell
.\run_workflow.ps1
```

### Direct Command Mode
Pass your prompt directly as a string:
```powershell
.\run_workflow.ps1 "Payment service failing intermittently for EU users"
```

## 📊 Observability

- **Logs**: Detailed execution logs are written to the `logs/` directory in JSONL format.
- **Console Output**: The Orchestrator provides real-time feedback on:
    - Intent Analysis
    - Plan Generation (with reasoning)
    - Agent Execution Steps
    - Final Results

## 🧩 Modifying the System

- **Add New Agents**:
    1. Create class in `collab_agents/`.
    2. Register metadata in `langgraph_agents/agent_registry.json`.
    3. Update import mapping in `smart_orchestrator.py`.
- **Update Policies**: Edit JSON files in `policies/` to change behavior without touching code.

## 📄 Documentation
See [architecture.md](architecture.md) for a deep dive into the Modular Monolith design, Hybrid Guardrails, and TOON optimization.

