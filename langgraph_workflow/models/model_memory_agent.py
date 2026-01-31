from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, Union

class MemoryInput(BaseModel):
    operation: Literal["read", "write", "update", "delete"]
    memory_type: Literal["working", "episodic", "semantic"]
    key: Optional[str] = Field(None, description="Key for read/delete operations.")
    content: Optional[Dict[str, Any]] = Field(None, description="Data to write/update.")
    user_id: str = Field(..., description="User ID context.")
    session_id: str = Field(..., description="Session ID context.")

class MemoryResult(BaseModel):
    success: bool
    data: Optional[Union[Dict[str, Any], Any]] = Field(None, description="Retrieved data.")
    message: Optional[str] = None
    timestamp: str

class MemoryOutput(BaseModel):
    result: MemoryResult
