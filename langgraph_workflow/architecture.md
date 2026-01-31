# AI Agentic Workflow Architecture

## 1. Executive Summary

This project implements a **Registry-Driven, Event-Based Multi-Agent System** designed for dynamic workflow orchestration. Unlike static state machines, this architecture uses an LLM-based **Smart Orchestrator** to analyze user intent and dynamically construct execution plans (DAGs) from a registry of available agents.

Key architectural features include:

- **Modular Monolith**: Agents are decoupled via an Event Bus but run in a single process for performance.
- **Configurable Policy Pattern**: Business logic (SLAs, Safety, Routing) is externalized into JSON policies.
- **TOON Optimization**: A custom "Token-Oriented Object Notation" layer reduces LLM interactions costs by 20-40%.
- **Hybrid Guardrails**: Safety is enforced via both Regex (fast) and Semantic LLM (smart) layers.

---

## 2. System Architecture Diagram

```mermaid
graph TD
    User[User / API] -->|Input| Orch[Smart Orchestrator]
    
    subgraph "Orchestration Layer"
        Orch -->|1. Analyze| NLP[NLP Service]
        NLP -->|2. Check Safety| Policy[Policy Engine]
        Orch -->|3. Load Specs| Reg[Agent Registry]
        Orch -->|4. Generate Plan| Planner[Planner Agent]
    end

    subgraph "Execution Layer (Event Bus)"
        Planner -->|Dispatch| EB[Event Bus]
        
        EB -->|Trigger| Ag1[Ingestion Agent]
        EB -->|Trigger| Ag2[Intent Agent]
        EB -->|Trigger| Ag3[Retrieval Agent]
        EB -->|Trigger| Ag4[Reasoning Agent]
        
        Ag1 <--> State[State Store (Async)]
        Ag2 <--> State
        Ag3 <--> State
    end

    subgraph "Optimization Layer"
        LLM_Client[LLM Client] -->|Encode| TOON[TOON Converter]
        TOON -->|Compact Prompt| Model[Mistral / OpenAI]
        Model -->|Compact Response| TOON
        TOON -->|Decode| LLM_Client
    end

    Ag2 -->|Call| LLM_Client
    Ag3 -->|Call| LLM_Client
    Ag4 -->|Call| LLM_Client

    Orch -->|Result| User
```

---

## 3. Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core runtime. |
| **Orchestration** | Custom / LangGraph | Dynamic DAG construction and state management. |
| **LLM Provider** | Mistral AI | Primary inference engine (via API). |
| **Data Validation** | Pydantic | Strict schema enforcement for Agent I/O. |
| **Optimization** | TOON (Custom) | JSON-to-Text compression for token efficiency. |
| **Vector Store** | ChromaDB* | (Design) For document retrieval. |
| **Logging** | CommonLogger | Structured JSONL logging for audit trails. |
| **Workflow** | Event-Driven | Asyncio-based EventBus pattern. |

*\*Note: Vector Store integration via configuration.*

---

## 4. Core Design Patterns

### 4.1. Registry-Driven Discovery

Agents are not hard-wired. The `SmartOrchestrator` loads `agent_registry.json` at runtime to understand:

- **Capabilities**: What the agent can do (keywords).
- **Input/Output Schema**: Pydantic definitions.
- **Cost/Time Estimates**: For planning logic.

### 4.2. Configurable Policy Pattern

Hardcoded business logic is avoided. Agents load behavior from the `policies/` directory:

- `intent_config.json`: Categories, SLA thresholds.
- `safety_policy.json`: Regex patterns, Semantic guidelines.
- `planner_rules.json`: Strategy decisions (Serial vs Parallel).

### 4.3. TOON (Token-Oriented Object Notation)

To reduce API costs, the `LLMClient` automatically converts verbose JSON payloads into a compact format before sending to the LLM.

- **Flow**: `Dict` -> `TOON String` -> `LLM` -> `TOON String` -> `Dict`
- **Mechanism**: Auto-generated short-key mappings (e.g., `primary_intent` -> `pi`).

### 4.4. Hybrid Guardrails

Safety runs in two stages:

1. **Fast Layer**: Regex matching (ms latency) for PII/known attacks.
2. **Smart Layer**: LLM-as-a-Judge (s latency) for semantic violations (tone, competitors).

---

## 5. Data Flow Description

1. **Input**: User sends a request (CLI or API).
2. **Analysis**: `SmartOrchestrator` calls `NLPService` to classify intent and check safety.
3. **Planning**: `PlannerAgent` references `planner_rules.json` to decide if the workflow should be Serial, Parallel, or complex DAG.
4. **Execution**:
    - Agents subscribe to the `EventBus`.
    - When dependencies are met (data available in `StateStore`), agents trigger.
    - Agents read input state, process (via LLM), and write output state.
5. **Completion**: Results are aggregated and returned.

---

## 6. Directory Structure Role

- `langgraph_agents/`: Core framework (Orchestrator, System, Main).
- `collab_agents/`: Domain-specific agents (Support, Planning).
- `policies/`: Configuration files (Business Rules).
- `models/`: Pydantic data contracts.
- `utils/`: Shared services (NLP, Logging, TOON).
