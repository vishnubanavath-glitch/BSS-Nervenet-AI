from typing import List, Optional
import uuid
from conversation.models.message import ChatMessage
from conversation.models.session import ChatSession
from conversation.repositories.history_repository import HistoryRepository

class DjangoHistoryStore(HistoryRepository):
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
        msg_id = uuid.UUID(str(message_id)) if message_id else uuid.uuid4()
        
        # Check that session exists (using async get)
        session = await ChatSession.objects.aget(session_id=session_id)
        
        msg = ChatMessage(
            message_id=msg_id,
            session=session,
            role=role,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost
        )
        await msg.asave()
        return msg

    async def get_recent_messages(self, session_id: str, limit: int) -> List[ChatMessage]:
        messages = []
        # Get the most recent limit messages, ordered descending by created_at, then reverse back to chronological.
        qs = ChatMessage.objects.filter(session_id=session_id).order_by("-created_at", "-message_id")[:limit]
        async for msg in qs:
            messages.append(msg)
        return list(reversed(messages))

    async def get_full_history(self, session_id: str) -> List[ChatMessage]:
        messages = []
        async for msg in ChatMessage.objects.filter(session_id=session_id).order_by("created_at"):
            messages.append(msg)
        return messages

    async def delete_history(self, session_id: str) -> bool:
        deleted_count, _ = await ChatMessage.objects.filter(session_id=session_id).adelete()
        return deleted_count > 0

    async def count_messages(self, session_id: str) -> int:
        return await ChatMessage.objects.filter(session_id=session_id).acount()
