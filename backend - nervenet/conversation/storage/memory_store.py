from typing import Optional, Dict, Any
from conversation.models.memory import ConversationMemory
from conversation.models.session import ChatSession
from conversation.repositories.memory_repository import MemoryRepository

class DjangoMemoryStore(MemoryRepository):
    async def get_memory(self, session_id: str) -> Optional[ConversationMemory]:
        try:
            return await ConversationMemory.objects.aget(session_id=session_id)
        except ConversationMemory.DoesNotExist:
            return None

    async def update_memory(self, session_id: str, memory_json: Dict[str, Any]) -> ConversationMemory:
        session = await ChatSession.objects.aget(session_id=session_id)
        
        memory, created = await ConversationMemory.objects.aget_or_create(
            session=session,
            defaults={"memory_json": memory_json}
        )
        if not created:
            merged = dict(memory.memory_json)
            merged.update(memory_json)
            memory.memory_json = merged
            
        import json
        memory_str = json.dumps(memory.memory_json)
        memory.token_count = max(0, len(memory_str) // 4)
        await memory.asave()
        return memory

    async def delete_memory(self, session_id: str) -> bool:
        try:
            memory = await ConversationMemory.objects.aget(session_id=session_id)
            await memory.adelete()
            return True
        except ConversationMemory.DoesNotExist:
            return False
