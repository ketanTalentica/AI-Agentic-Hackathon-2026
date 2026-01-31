from pydantic import BaseModel, Field
from typing import Optional, List
from .model_ingestion_agent import NormalizedPayload

class IntentInput(BaseModel):
    normalized_payload: NormalizedPayload

class IntentClassification(BaseModel):
    primary_intent: str = Field(..., description="The main intent detected (e.g., 'technical_support', 'billing').")
    confidence_score: float = Field(..., description="Confidence level of the intent classification (0.0 to 1.0).")
    urgency_level: str = Field(..., description="detected urgency: 'low', 'medium', 'high', 'critical'.")
    sla_risk_score: float = Field(default=0.0, description="Probability of breaching SLA (0.0 to 1.0).")
    secondary_intents: List[str] = Field(default_factory=list, description="Other potential intents detected.")
    reasoning: Optional[str] = Field(None, description="Explanation for calculation.")

class IntentOutput(BaseModel):
    classification: IntentClassification
