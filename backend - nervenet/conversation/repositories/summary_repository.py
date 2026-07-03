from abc import ABC, abstractmethod
from typing import Optional
from conversation.models.summary import ConversationSummary

class SummaryRepository(ABC):
    @abstractmethod
    async def get_summary(self, session_id: str) -> Optional[ConversationSummary]:
        """Retrieve the summary of the conversation for a session."""
        pass

    @abstractmethod
    async def update_summary(
        self,
        session_id: str,
        summary_text: str,
        last_processed_message_id: Optional[str] = None
    ) -> ConversationSummary:
        """Update/set the summary for a session."""
        pass

    @abstractmethod
    async def delete_summary(self, session_id: str) -> bool:
        """Delete summary associated with a session."""
        pass
