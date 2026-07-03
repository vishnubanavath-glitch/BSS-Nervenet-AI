import pytest
from conversation.models.session import SessionStatus
from conversation.exceptions import SessionNotFoundException, ValidationError
from conversation.utils.helpers import generate_uuid

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_session_lifecycle(conversation_manager):
    session_id = generate_uuid()
    
    # Create session
    session = await conversation_manager._session_manager.create_session(session_id, "Test Title")
    assert str(session.session_id) == session_id
    assert session.title == "Test Title"
    assert session.status == SessionStatus.ACTIVE
    
    # Load session
    loaded = await conversation_manager._session_manager.load_session(session_id)
    assert str(loaded.session_id) == session_id
    assert loaded.title == "Test Title"
    
    # Update session title
    loaded.title = "Updated Title"
    updated = await conversation_manager._session_manager.update_session(loaded)
    assert updated.title == "Updated Title"
    
    # Update last activity
    updated_again = await conversation_manager._session_manager.update_last_activity(session_id)
    assert updated_again.updated_at is not None
    
    # Assert validation check succeeds
    await conversation_manager._session_manager.validate_session_exists(session_id)
    
    # Delete session
    deleted = await conversation_manager._session_manager.delete_session(session_id)
    assert deleted is True
    
    # Loading after delete should raise SessionNotFoundException
    with pytest.raises(SessionNotFoundException):
        await conversation_manager._session_manager.load_session(session_id)

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_invalid_session_id(conversation_manager):
    with pytest.raises(ValidationError):
        await conversation_manager._session_manager.create_session("invalid-uuid-string")
