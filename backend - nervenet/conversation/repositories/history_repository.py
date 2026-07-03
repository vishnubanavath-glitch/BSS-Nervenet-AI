from abc import ABC, abstractmethod
from typing import List, Optional
from conversation.models.message import ChatMessage

class HistoryRepository(ABC):
    @abstractmethod
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
        """Add a message to the conversation history."""
        pass

    @abstractmethod
    async def get_recent_messages(self, session_id: str, limit: int) -> List[ChatMessage]:
        """Get the most recent messages, up to a specified limit."""
        pass

    @abstractmethod
    async def get_full_history(self, session_id: str) -> List[ChatMessage]:
        """Get the complete history for a session."""
        pass

    @abstractmethod
    async def delete_history(self, session_id: str) -> bool:
        """Delete all messages associated with a session."""
        pass

    @abstractmethod
    async def count_messages(self, session_id: str) -> int:
        """Count the number of messages in a session."""
        pass
