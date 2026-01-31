# LangGraph Multi-Agent Workflow Architecture

This folder contains the starter architecture and code templates for a modular multi-agent workflow executor using LangGraph and Mistral AI.

## Structure
- `orchestrator.py` — Orchestrator agent managing workflow, state, and user interaction.
- `agents/` — Worker agent modules (content generation, scheduling, API calls, etc.).
- `llm_client.py` — LLM abstraction layer (Mistral AI, configurable).
- `workflow_definition.py` — Example workflow definition (sequence/graph of tasks).
- `config.py` — Configuration for LLM keys, endpoints, etc.

## Usage
- Plug in new worker agents as needed.
- Define new workflows by updating `workflow_definition.py`.
- Orchestrator remains reusable for any workflow.

---
This template is designed for easy integration with .NET and Angular frontends.
