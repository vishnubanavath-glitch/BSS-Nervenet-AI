from typing import Optional, List
from conversation.models.session import ChatSession, SessionStatus
from conversation.repositories.session_repository import SessionRepository

class DjangoSessionStore(SessionRepository):
    async def create(self, session_id: str, title: Optional[str] = None) -> ChatSession:
        session = ChatSession(session_id=session_id, title=title)
        await session.asave()
        return session

    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        try:
            return await ChatSession.objects.aget(session_id=session_id)
        except ChatSession.DoesNotExist:
            return None

    async def update(self, session: ChatSession) -> ChatSession:
        await session.asave()
        return session

    async def delete(self, session_id: str) -> bool:
        try:
            session = await ChatSession.objects.aget(session_id=session_id)
            await session.adelete()
            return True
        except ChatSession.DoesNotExist:
            return False

    async def list_active(self) -> List[ChatSession]:
        sessions = []
        async for session in ChatSession.objects.filter(status=SessionStatus.ACTIVE):
            sessions.append(session)
        return sessions
