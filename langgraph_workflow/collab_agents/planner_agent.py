from langgraph_agents.langgraph_system import BaseAgent
from typing import Dict, Any, List, Optional
import json
import os
import logging
from enum import Enum
from pydantic import ValidationError

# Import Models
try:
    from models.model_intent_agent import IntentClassification
    from models.model_planner_agent import ExecutionPlan, WorkflowStep, PlannerOutput
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.append("..")
    from models.model_intent_agent import IntentClassification
    from models.model_planner_agent import ExecutionPlan, WorkflowStep, PlannerOutput

class ExecutionStrategy(Enum):
    SERIAL = "serial"
    PARALLEL = "parallel"
    DYNAMIC_DAG = "dynamic_dag"

class PlannerAgent(BaseAgent):
    """
    AGENT: Planner / Orchestrator Agent
    DESCRIPTION: Decides execution strategy: serial, parallel, or async.
    CAPABILITIES: planning, delegation, strategy_optimization, orchestration
    OWNS: [PRD 3.3 & 3.7] Context Management (Pruning), Workflow Decisions (Serial vs Parallel), and Task Delegation.
    REQUIRED_PACKAGES: networkx
    """
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.logger = logging.getLogger("PlannerAgent")
        self.registry = self._load_json_config("langgraph_agents", "agent_registry.json")
        self.rules = self._load_json_config("policies", "planner_rules.json")

    def _load_json_config(self, folder: str, filename: str) -> Dict[str, Any]:
        """Generic loader for JSON config files."""
        try:
            path = os.path.join(os.path.dirname(os.path.dirname(__file__)), folder, filename)
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config {filename}: {e}")
            return {}

    async def _execute_impl(self) -> Dict[str, Any]:
        """
        Implementation of planning logic (Serial vs Parallel).
        Planner now works independently of Intent Agent - follows diagram flow.
        """
        self.logger.info("Planner Agent executing...")

        # 1. READ INPUT: Get Ingestion Data from State
        # Planner analyzes the ingested data and creates execution strategy
        ingestion_data = await self.state_store.get("ingestion_output")
        
        if not ingestion_data:
            self.logger.warning("No ingestion data found. Defaulting to basic serial flow.")
            return self._create_fallback_plan()

        # 2. ANALYZE REQUEST: Determine workflow type from ingestion data
        # Use simple heuristics on the raw request to decide strategy
        template_key, strategy = self._decide_strategy_from_ingestion(ingestion_data)
        
        self.logger.info(f"Selected Template: {template_key}, Strategy: {strategy.value}")

        # 3. BUILD DAG: Construct the specific steps
        execution_plan = self._build_execution_graph(template_key, strategy, ingestion_data)

        # 4. OUTPUT: Return the Plan object
        return {
            "execution_plan": execution_plan.model_dump(),
            "status": "plan_ready"
        }

    def _decide_strategy_from_ingestion(self, ingestion_data: Dict[str, Any]) -> tuple[str, ExecutionStrategy]:
        """
        The 'Brain' of the Planner.
        Decides workflow strategy based on ingestion data (before Intent classification).
        Uses keyword heuristics to determine the best template and execution mode.
        """
        # Extract raw text from ingestion
        raw_text = ingestion_data.get("processed_text", "").lower()
        metadata = ingestion_data.get("metadata", {})
        
        # Simple keyword-based heuristics
        # For production, this could use lightweight NLP or rule matching
        
        # Check for urgent/critical keywords
        urgent_keywords = ["urgent", "critical", "emergency", "down", "outage", "broken", "failed"]
        is_urgent = any(keyword in raw_text for keyword in urgent_keywords)
        
        # Check for investigation keywords (requires parallel research)
        investigation_keywords = ["why", "analyze", "investigate", "root cause", "pattern", "trend"]
        needs_investigation = any(keyword in raw_text for keyword in investigation_keywords)
        
        # Check for simple query keywords
        query_keywords = ["how to", "what is", "can you", "please", "help"]
        is_simple_query = any(keyword in raw_text for keyword in query_keywords)
        
        # Decision logic
        if is_urgent:
            # Critical issues: Use parallel strategy for faster response
            return "incident_response", ExecutionStrategy.PARALLEL
        elif needs_investigation:
            # Complex investigation: Use parallel for comprehensive analysis
            return "root_cause_analysis", ExecutionStrategy.PARALLEL
        elif is_simple_query:
            # Simple questions: Serial flow is sufficient
            return "customer_support_ticket", ExecutionStrategy.SERIAL
        else:
            # Default: Customer support with serial execution
            return "customer_support_ticket", ExecutionStrategy.SERIAL
    
    def _decide_strategy(self, intent: IntentClassification) -> tuple[str, ExecutionStrategy]:
        """
        Legacy method: Decides mechanism based on intent classification.
        Kept for backward compatibility if needed.
        """
        intent_dict = intent.model_dump()
        rules = self.rules.get("strategy_rules", [])
        
        # Sort rules by priority (1 is highest)
        sorted_rules = sorted(rules, key=lambda x: x.get("priority", 999))

        for rule in sorted_rules:
            condition = rule.get("condition", {})
            field_name = condition.get("field")
            operator = condition.get("operator")
            target_value = condition.get("value")
            
            actual_value = intent_dict.get(field_name)
            
            match = False
            if operator == "in":
                if isinstance(target_value, list) and actual_value in target_value:
                    match = True
            elif operator == "==":
                if actual_value == target_value:
                    match = True
            elif operator == ">":
                if isinstance(actual_value, (int, float)) and actual_value > target_value:
                    match = True
            
            if match:
                action = rule.get("action", {})
                return action.get("template"), ExecutionStrategy(action.get("strategy"))

        # Default fallback from config
        default = self.rules.get("default_strategy", {})
        return default.get("template", "customer_support_ticket"), ExecutionStrategy(default.get("strategy", "serial"))

    def _build_execution_graph(self, template_key: str, strategy: ExecutionStrategy, ingestion_data: Dict[str, Any]) -> ExecutionPlan:
        """
        Constructs the list of WorkflowSteps based on the registry template and selected strategy.
        """
        template = self.registry.get("workflow_templates", {}).get(template_key, {})
        agent_list = template.get("typical_agents", [])
        
        steps = []
        
        # Filter out agents that have already run (Ingestion, Planner)
        # Intent will run AFTER Planner per the diagram
        remaining_agents = [
            a for a in agent_list 
            if a not in ["ingestion_agent", "planner_agent"]
        ]

        if strategy == ExecutionStrategy.SERIAL:
            # Chain them one after another: A -> B -> C
            previous_step_id = "planner_agent" # Planner is the predecessor
            
            for agent_name in remaining_agents:
                step_id = f"step_{agent_name}"
                step = WorkflowStep(
                    step_id=step_id,
                    agent_name=agent_name,
                    description=f"Execute {agent_name}",
                    dependencies=[previous_step_id]
                )
                steps.append(step)
                previous_step_id = step_id

        elif strategy == ExecutionStrategy.PARALLEL:
            # Identify 'Research' agents that can run together
            # Typically: Retrieval, Memory, and Reasoning (maybe)
            
            parallel_group = []
            serial_group = [] 
            
            # Simple heuristic: Retrieval and Memory are independent read ops -> Parallel
            for agent_name in remaining_agents:
                if agent_name in ["retrieval_agent", "memory_agent"]:
                    parallel_group.append(agent_name)
                else:
                    serial_group.append(agent_name)
            
            # 1. Run Parallel Batch
            parallel_step_ids = []
            for agent_name in parallel_group:
                step_id = f"step_{agent_name}"
                step = WorkflowStep(
                    step_id=step_id,
                    agent_name=agent_name,
                    description=f"Parallel execution of {agent_name}",
                    dependencies=["planner_agent"], # Depending on Start
                    parallel_group_id="context_gathering_phase"
                )
                steps.append(step)
                parallel_step_ids.append(step_id)
            
            # 2. Run Subsequent Serial Batch (depending on ALL parallel steps)
            previous_deps = parallel_step_ids
            for agent_name in serial_group:
                step_id = f"step_{agent_name}"
                step = WorkflowStep(
                    step_id=step_id,
                    agent_name=agent_name,
                    description=f"Execute {agent_name}",
                    dependencies=previous_deps
                )
                steps.append(step)
                previous_deps = [step_id] # Next step depends on this one

        else: # DYNAMIC_DAG (Default Fallback to Serial for now)
             # Logic for advanced branching goes here
             return self._build_execution_graph(template_key, ExecutionStrategy.SERIAL, intent)

        return ExecutionPlan(
            plan_id=f"plan_{template_key}_{strategy.value}",
            strategy=strategy.value,
            steps=steps
        )

    def _create_fallback_plan(self) -> Dict[str, Any]:
        """Production safe-guard: If planning fails, return a safe minimal path."""
        self.logger.error("Creating Fallback Plan due to error.")
        
        # Fallback: Just try to synthesize a response directly (maybe asking for more info)
        fallback_step = WorkflowStep(
            step_id="step_response_synthesis",
            agent_name="response_synthesis_agent",
            description="Fallback synthesis",
            dependencies=[]
        )
        
        plan = ExecutionPlan(
            plan_id="fallback_plan",
            strategy="serial",
            steps=[fallback_step]
        )
        
        return {"execution_plan": plan.model_dump()}
