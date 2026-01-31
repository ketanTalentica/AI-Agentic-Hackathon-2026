from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class RetrievalInput(BaseModel):
    search_query: str = Field(..., description="The semantic search query.")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters (e.g., {'doc_type': 'pdf'}).")
    top_k: int = Field(default=5, description="Number of chunks to retrieve.")

class ContextChunk(BaseModel):
    chunk_id: str
    content: str = Field(..., description="The actual text content of the chunk.")
    source_document: str = Field(..., description="Filename or URI of the source.")
    page_number: Optional[int] = None
    media_type: str = Field(default="text/plain", description="MIME type (text/plain, image/png, etc.).")
    embedding_score: float = Field(..., description="Similarity score.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RetrievalOutput(BaseModel):
    retrieved_context: List[ContextChunk]
