from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class IngestionInput(BaseModel):
    raw_input: str = Field(..., description="The raw, unprocessed input text or data from the user.")
    source_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata about the source (e.g., channel='email', sender='user@example.com', timestamp).")

class NormalizedPayload(BaseModel):
    request_id: str = Field(..., description="Unique ID for this request.")
    cleaned_text: str = Field(..., description="Sanitized and normalized text content.")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Any extracted structured data from the raw input.")
    original_source: Dict[str, Any] = Field(default_factory=dict, description="Preserved source metadata.")
    
class IngestionOutput(BaseModel):
    normalized_payload: NormalizedPayload
