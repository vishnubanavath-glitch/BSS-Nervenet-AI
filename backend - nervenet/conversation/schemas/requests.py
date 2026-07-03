from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="Optional title for the new session")

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Content of the user message")
    role: str = Field("user", description="Role of the sender (defaults to user)")
    memory_updates: Optional[Dict[str, Any]] = Field(None, description="Temporary runtime memory context updates")
