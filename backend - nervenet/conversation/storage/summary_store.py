from typing import Optional
import uuid
from conversation.models.summary import ConversationSummary
from conversation.models.session import ChatSession
from conversation.repositories.summary_repository import SummaryRepository

class DjangoSummaryStore(SummaryRepository):
    async def get_summary(self, session_id: str) -> Optional[ConversationSummary]:
        try:
            return await ConversationSummary.objects.aget(session_id=session_id)
        except ConversationSummary.DoesNotExist:
            return None

    async def update_summary(
        self,
        session_id: str,
        summary_text: str,
        last_processed_message_id: Optional[str] = None
    ) -> ConversationSummary:
        session = await ChatSession.objects.aget(session_id=session_id)
        
        last_msg_uuid = uuid.UUID(last_processed_message_id) if last_processed_message_id else None
        
        summary, created = await ConversationSummary.objects.aget_or_create(
            session=session,
            defaults={
                "summary": summary_text,
                "last_processed_message_id": last_msg_uuid,
                "token_count": max(0, len(summary_text) // 4)
            }
        )
        if not created:
            summary.summary = summary_text
            summary.last_processed_message_id = last_msg_uuid
            summary.token_count = max(0, len(summary_text) // 4)
            await summary.asave()
        return summary

    async def delete_summary(self, session_id: str) -> bool:
        try:
            summary = await ConversationSummary.objects.aget(session_id=session_id)
            await summary.adelete()
            return True
        except ConversationSummary.DoesNotExist:
            return False
