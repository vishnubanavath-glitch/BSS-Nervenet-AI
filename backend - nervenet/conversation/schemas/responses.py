from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

class TokenUsageSchema(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float

class SessionResponse(BaseModel):
    session_id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    status: str

class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: datetime
    token_usage: Optional[TokenUsageSchema] = None

class ChatResponse(BaseModel):
    session_id: str
    response_content: str
    role: str = "assistant"
    recent_history: List[MessageResponse]
    memory: Dict[str, Any]
    summary: Optional[str] = None
    token_usage: TokenUsageSchema
