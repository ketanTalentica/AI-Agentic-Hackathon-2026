from langgraph_agents.langgraph_system import BaseAgent
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
import re
import json
from utils.CommonLogger import CommonLogger
from config import UTILS_LOG_DIR_PATH

# --- Pydantic Models for Validation ---

class IngestionInput(BaseModel):
    """Schema for the raw input expected by IngestionAgent"""
    user_input: str = Field(..., description="The raw text provided by the user.")
    source_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the source (e.g., UI, API, Email).")

class NormalizedPayload(BaseModel):
    """Schema for the standardized output"""
    raw_input: str
    cleaned_text: str
    ingestion_timestamp: str
    request_id: str
    metadata: Dict[str, Any]
    is_valid: bool = True
    error_message: Optional[str] = None

# --- Agent Implementation ---

class IngestionAgent(BaseAgent):
    """
    AGENT: Ingestion Agent
    DESCRIPTION: Normalizes incoming tickets and queries to standardized format.
    CAPABILITIES: input_normalization, request_standardization, basic_sanitization
    OWNS: [PRD 4.1] Data Cleaning, Request Normalization.
    REQUIRED_PACKAGES: pydantic
    """
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.log_path = UTILS_LOG_DIR_PATH + "ingestion_agent.log"
        # Simple regex for removing excessive whitespace and non-printable characters
        self.cleaning_pattern = re.compile(r'\s+')

    async def _execute_impl(self) -> Dict[str, Any]:
        """
        Executes the ingestion logic:
        1. Validates input schema.
        2. Cleanses text (whitespace, basic control chars).
        3. Enriches with metadata (timestamps).
        4. Returns normalized payload.
        """
        raw_state = self.state_store.get_all()
        user_input_data = raw_state.get("user_input", {})

        # Handle different input formats (string vs dict)
        if isinstance(user_input_data, str):
            payload = {"user_input": user_input_data}
        else:
            payload = user_input_data

        CommonLogger.WriteLog(self.log_path, f"[{datetime.now().isoformat()}] Received raw payload: {json.dumps(payload, default=str)}")

        try:
            # 1. Validation
            validated_input = IngestionInput(**payload)
            
            # 2. Cleaning & Normalization
            cleaned_text = self._clean_text(validated_input.user_input)
            
            # 3. Enrichment
            normalized_output = NormalizedPayload(
                raw_input=validated_input.user_input,
                cleaned_text=cleaned_text,
                ingestion_timestamp=datetime.utcnow().isoformat() + "Z",
                request_id=self._generate_request_id(),
                metadata=validated_input.source_metadata
            )

            CommonLogger.WriteLog(self.log_path, f"[{datetime.now().isoformat()}] Normalized success: {normalized_output.model_dump_json()}")

            # Return keyed by 'normalized_payload' as expected by IntentAgent
            return {
                "normalized_payload": normalized_output.model_dump(),
                "ingestion_status": "success"
            }

        except ValidationError as e:
            error_msg = f"Validation failed: {e}"
            CommonLogger.WriteLog(self.log_path, f"[ERROR] {error_msg}")
            
            # Fail gracefully by passing the error state
            return {
                "normalized_payload": None,
                "ingestion_status": "failed",
                "ingestion_error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected ingestion error: {str(e)}"
            CommonLogger.WriteLog(self.log_path, f"[CRITICAL] {error_msg}")
            return {
                "normalized_payload": None,
                "ingestion_status": "error",
                "ingestion_error": error_msg
            }

    def _clean_text(self, text: str) -> str:
        """Removes excessive whitespace and strips text."""
        if not text:
            return ""
        # Collapse multiple spaces to one
        text = self.cleaning_pattern.sub(' ', text)
        return text.strip()

    def _generate_request_id(self) -> str:
        """Generates a simple unique ID for the request (mock implementation)."""
        import uuid
        return str(uuid.uuid4())

