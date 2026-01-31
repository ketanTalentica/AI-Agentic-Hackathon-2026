from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from .model_reasoning_agent import ReasoningTrace

class SynthesisInput(BaseModel):
    reasoning_trace: ReasoningTrace
    user_intent: str = Field(..., description="Original user intent to align tone.")
    tone_guidelines: Optional[str] = Field("professional and helpful", description="Instructions for tone.")

class SynthesisOutput(BaseModel):
    final_response: str = Field(..., description="The human-readable response string.")
    citations: List[str] = Field(default_factory=list, description="References used in the response.")
    meta_info: Dict[str, Any] = Field(default_factory=dict)
