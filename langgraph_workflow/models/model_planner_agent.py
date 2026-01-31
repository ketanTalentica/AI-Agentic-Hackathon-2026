from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any
from .model_intent_agent import IntentClassification

class PlannerInput(BaseModel):
    intent_data: IntentClassification
    available_agents: List[str] = Field(default_factory=list, description="List of currently available agents to plan with.")

class WorkflowStep(BaseModel):
    step_id: str
    agent_name: str
    description: str
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Static inputs or reference keys.")
    dependencies: List[str] = Field(default_factory=list, description="List of step_ids that must complete before this step.")
    parallel_group_id: Optional[str] = Field(None, description="If steps share a group ID, they can run in parallel.")

class ExecutionPlan(BaseModel):
    plan_id: str
    strategy: Literal["serial", "parallel", "dynamic_dag"] = Field(..., description="The high-level execution strategy.")
    steps: List[WorkflowStep]
    estimated_latency_ms: Optional[float] = None

class PlannerOutput(BaseModel):
    execution_plan: ExecutionPlan
