from typing import List, Optional
from conversation.models.message import ChatMessage
from conversation.repositories.history_repository import HistoryRepository
from conversation.utils.validators import validate_uuid, validate_role

class HistoryManager:
    def __init__(self, history_repo: HistoryRepository):
        self._history_repo = history_repo

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        estimated_cost: Optional[float] = None
    ) -> ChatMessage:
        """Validate role/IDs, and save the message using the repository."""
        validate_uuid(session_id)
        if message_id:
            validate_uuid(message_id)
        validate_role(role)
        
        return await self._history_repo.add_message(
            session_id=session_id,
            role=role,
            content=content,
            message_id=message_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost
        )

    async def get_recent_messages(self, session_id: str, limit: int) -> List[ChatMessage]:
        """Fetch the most recent messages up to a limit."""
        validate_uuid(session_id)
        return await self._history_repo.get_recent_messages(session_id, limit)

    async def get_complete_history(self, session_id: str) -> List[ChatMessage]:
        """Fetch all messages for the session."""
        validate_uuid(session_id)
        return await self._history_repo.get_full_history(session_id)

    async def delete_history(self, session_id: str) -> bool:
        """Clear all messages from history for the session."""
        validate_uuid(session_id)
        return await self._history_repo.delete_history(session_id)

    async def count_messages(self, session_id: str) -> int:
        """Count total messages in the session."""
        validate_uuid(session_id)
        return await self._history_repo.count_messages(session_id)
