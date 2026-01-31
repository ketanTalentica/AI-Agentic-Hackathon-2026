# Dynamic workflow definition
# NOTE: This file is kept for backward compatibility but is largely superseded by
# the 'planner_agent' which constructs the graph dynamically at runtime.

WORKFLOW_STEPS = [
    # Core Agents
    {"worker": "ingestion_agent"},
    {"worker": "intent_agent"},
    {"worker": "planner_agent"},
    
    # Conditional Execution Agents (Called by Planner)
    {"worker": "retrieval_agent"},
    {"worker": "memory_agent"},
    {"worker": "reasoning_agent"},
    {"worker": "response_synthesis_agent"},
    
    # Safety
    {"worker": "guardrails_agent"},
]

# Legacy steps (preserved if needed)
LEGACY_WORKFLOW_STEPS = [
    {"worker": "interpreter_agent"},
    {"worker": "content_generator"},
    {"worker": "plan_presenter"}
]
