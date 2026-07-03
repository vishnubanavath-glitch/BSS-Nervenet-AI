from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from conversation.models.memory import ConversationMemory

class MemoryRepository(ABC):
    @abstractmethod
    async def get_memory(self, session_id: str) -> Optional[ConversationMemory]:
        """Retrieve the temporary memory context for a session."""
        pass

    @abstractmethod
    async def update_memory(self, session_id: str, memory_json: Dict[str, Any]) -> ConversationMemory:
        """Update/merge the temporary memory context for a session."""
        pass

    @abstractmethod
    async def delete_memory(self, session_id: str) -> bool:
        """Delete memory associated with a session."""
        pass
