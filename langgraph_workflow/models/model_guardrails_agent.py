from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class SafetyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    ESCALATE = "escalate"

class GuardrailsInput(BaseModel):
    proposed_response: str
    context_summary: Optional[str] = None

class SafetyViolation(BaseModel):
    category: str = Field(description="e.g., 'pii', 'toxicity', 'hallucination'.")
    severity: str = Field(description="'low', 'medium', 'high'.")
    details: str

class GuardrailsOutput(BaseModel):
    action: SafetyAction
    safe_response: str = Field(..., description="The final response text (clean).")
    violations: List[SafetyViolation] = Field(default_factory=list)
