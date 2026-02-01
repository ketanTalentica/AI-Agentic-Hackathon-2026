from pydantic import BaseModel, Field
from typing import List, Dict, Any
from .model_retrieval_agent import ContextChunk

class ReasoningInput(BaseModel):
    context: List[ContextChunk] = Field(..., description="Retrieved context chunks.")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Relevant conversation history.")
    problem_statement: str = Field(..., description="The core issue to analyze.")

class RootCause(BaseModel):
    cause: str
    probability: float
    evidence: List[str] = Field(description="Quotes or references from context supporting this cause.")

class ActionStep(BaseModel):
    step: str
    details: str

class RecommendedSolution(BaseModel):
    immediate_actions: List[ActionStep] = Field(default_factory=list)
    long_term: List[ActionStep] = Field(default_factory=list)

class ReasoningTrace(BaseModel):
    analysis_steps: List[str] = Field(description="Step-by-step chain of thought.")
    identified_patterns: List[str] = Field(default_factory=list, description="Correlations with historical data.")
    root_causes: List[RootCause]
    recommended_solution: RecommendedSolution
    confidence_score: float

class ReasoningOutput(BaseModel):
    trace: ReasoningTrace
