from typing import Dict, Any, Optional
from conversation.models.memory import ConversationMemory
from conversation.repositories.memory_repository import MemoryRepository
from conversation.utils.validators import validate_uuid

class MemoryManager:
    def __init__(self, memory_repo: MemoryRepository):
        self._memory_repo = memory_repo

    async def get_memory(self, session_id: str) -> Dict[str, Any]:
        """Get the memory dictionary. Returns an empty dictionary if no memory exists."""
        validate_uuid(session_id)
        memory = await self._memory_repo.get_memory(session_id)
        if not memory:
            return {}
        return memory.memory_json

    async def update_memory(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update/merge memory values. Returns the merged dictionary."""
        validate_uuid(session_id)
        memory = await self._memory_repo.update_memory(session_id, updates)
        return memory.memory_json

    async def delete_memory(self, session_id: str) -> bool:
        """Delete all memory associated with this session."""
        validate_uuid(session_id)
        return await self._memory_repo.delete_memory(session_id)
