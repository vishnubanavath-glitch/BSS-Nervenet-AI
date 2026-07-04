from typing import Optional, List, Any
from conversation.models.summary import ConversationSummary
from conversation.models.message import ChatMessage
from conversation.repositories.summary_repository import SummaryRepository
from conversation.repositories.history_repository import HistoryRepository
from conversation.utils.validators import validate_uuid
from conversation.constants import PRESERVE_RECENT_MESSAGES_COUNT

class SummaryManager:
    def __init__(self, summary_repo: SummaryRepository, history_repo: HistoryRepository):
        self._summary_repo = summary_repo
        self._history_repo = history_repo

    async def get_summary(self, session_id: str) -> Optional[str]:
        """Fetch the summary text for a session. Returns None if no summary exists."""
        validate_uuid(session_id)
        summary = await self._summary_repo.get_summary(session_id)
        if not summary:
            return None
        return summary.summary

    async def get_summary_object(self, session_id: str) -> Optional[ConversationSummary]:
        """Fetch the full summary database object for a session."""
        validate_uuid(session_id)
        return await self._summary_repo.get_summary(session_id)

    async def update_summary(
        self,
        session_id: str,
        summary_text: str,
        last_processed_message_id: Optional[str] = None
    ) -> ConversationSummary:
        """Update the conversation summary and mark the last processed message."""
        validate_uuid(session_id)
        if last_processed_message_id:
            validate_uuid(last_processed_message_id)
        return await self._summary_repo.update_summary(session_id, summary_text, last_processed_message_id)

    async def delete_summary(self, session_id: str) -> bool:
        """Delete summary associated with a session."""
        validate_uuid(session_id)
        return await self._summary_repo.delete_summary(session_id)

    async def summarize_history(
        self,
        session_id: str,
        llm_manager,
        privacy_engine: Optional[Any] = None
    ) -> Optional[str]:
        """Condense older history into a consolidated summary block, preserving recent messages.
        
        Args:
            session_id: The UUID of the active session.
            llm_manager: The LLMManager instance used to request the summarization.
            privacy_engine: Optional privacy engine instance to tokenize raw PII in history before summarization.
        """
        validate_uuid(session_id)
        
        # 1. Fetch complete history
        messages = await self._history_repo.get_full_history(session_id)
        if len(messages) <= PRESERVE_RECENT_MESSAGES_COUNT:
            return await self.get_summary(session_id)
            
        # 2. Divide history: older messages to summarize vs. recent messages to keep active
        to_summarize = messages[:-PRESERVE_RECENT_MESSAGES_COUNT]
        
        # 3. Retrieve existing summary
        existing_summary_obj = await self._summary_repo.get_summary(session_id)
        existing_summary = existing_summary_obj.summary if existing_summary_obj else ""
        
        # Tokenize existing summary if privacy engine is provided
        if privacy_engine and existing_summary:
            existing_summary = privacy_engine.tokenize_text(existing_summary)
            
        # 4. Format history, tokenizing user messages if privacy engine is provided
        history_lines = []
        for m in to_summarize:
            role = m.role
            content = m.content
            if role == "user" and privacy_engine:
                content = privacy_engine.tokenize_text(content)
            history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines)
        
        # 5. Build prompt
        prompt = (
            "You are a conversation summarization utility. Summarize the following chat history concisely.\n\n"
            f"Existing Summary:\n{existing_summary or 'None'}\n\n"
            f"New messages to incorporate:\n{history_text}\n\n"
            "Provide an updated, consolidated summary of the conversation so far."
        )
        
        # 6. Call LLM to generate the updated summary text
        response = await llm_manager.generate_response(prompt)
        new_summary = response.content.strip()
        
        # 7. Update storage
        last_msg = to_summarize[-1]
        await self.update_summary(
            session_id=session_id,
            summary_text=new_summary,
            last_processed_message_id=str(last_msg.message_id)
        )
        return new_summary
