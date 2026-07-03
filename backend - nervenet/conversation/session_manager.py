from typing import Optional, List
from conversation.models.session import ChatSession, SessionStatus
from conversation.repositories.session_repository import SessionRepository
from conversation.exceptions import SessionNotFoundException
from conversation.utils.validators import validate_uuid
from django.utils import timezone

class SessionManager:
    def __init__(self, session_repo: SessionRepository):
        self._session_repo = session_repo

    async def create_session(self, session_id: str, title: Optional[str] = None) -> ChatSession:
        """Create a new session using the repository."""
        validate_uuid(session_id)
        return await self._session_repo.create(session_id, title)

    async def load_session(self, session_id: str) -> ChatSession:
        """Load a session. Raises SessionNotFoundException if missing or deleted."""
        validate_uuid(session_id)
        session = await self._session_repo.get_by_id(session_id)
        if not session or session.status == SessionStatus.DELETED:
            raise SessionNotFoundException(f"Session with ID {session_id} not found.")
        return session

    async def update_session(self, session: ChatSession) -> ChatSession:
        """Save updates to the session."""
        return await self._session_repo.update(session)

    async def delete_session(self, session_id: str) -> bool:
        """Delete the session and all associated cascade data."""
        validate_uuid(session_id)
        return await self._session_repo.delete(session_id)

    async def update_last_activity(self, session_id: str) -> ChatSession:
        """Explicitly update the session's modification timestamp."""
        session = await self.load_session(session_id)
        session.updated_at = timezone.now()
        return await self._session_repo.update(session)

    async def validate_session_exists(self, session_id: str) -> None:
        """Helper to assert session existence."""
        await self.load_session(session_id)
