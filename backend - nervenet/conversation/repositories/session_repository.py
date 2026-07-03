from abc import ABC, abstractmethod
from typing import Optional, List
from conversation.models.session import ChatSession

class SessionRepository(ABC):
    @abstractmethod
    async def create(self, session_id: str, title: Optional[str] = None) -> ChatSession:
        """Create a new chat session."""
        pass

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        """Retrieve a session by its UUID."""
        pass

    @abstractmethod
    async def update(self, session: ChatSession) -> ChatSession:
        """Update an existing session."""
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session by its UUID."""
        pass

    @abstractmethod
    async def list_active(self) -> List[ChatSession]:
        """List all active sessions."""
        pass
