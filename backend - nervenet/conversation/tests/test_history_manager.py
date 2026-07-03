import pytest
import asyncio
from conversation.models.message import MessageRole
from conversation.exceptions import ValidationError
from conversation.utils.helpers import generate_uuid

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_history_management(conversation_manager):
    session_id = generate_uuid()
    
    # Pre-create session to avoid foreign key errors
    await conversation_manager._session_manager.create_session(session_id, "Test Session")
    
    # Store messages with tiny delays to ensure distinct database timestamps
    m1 = await conversation_manager._history_manager.add_message(session_id, "user", "Message 1")
    await asyncio.sleep(0.005)
    m2 = await conversation_manager._history_manager.add_message(session_id, "assistant", "Message 2")
    await asyncio.sleep(0.005)
    m3 = await conversation_manager._history_manager.add_message(session_id, "user", "Message 3")
    
    assert m1.role == MessageRole.USER
    assert m1.content == "Message 1"
    
    # Count messages
    count = await conversation_manager._history_manager.count_messages(session_id)
    assert count == 3
    
    # Retrieve complete history
    history = await conversation_manager._history_manager.get_complete_history(session_id)
    assert len(history) == 3
    assert history[0].content == "Message 1"
    assert history[1].content == "Message 2"
    assert history[2].content == "Message 3"
    
    # Retrieve recent messages with limit
    recent = await conversation_manager._history_manager.get_recent_messages(session_id, limit=2)
    assert len(recent) == 2
    assert recent[0].content == "Message 2"
    assert recent[1].content == "Message 3"
    
    # Validate invalid roles trigger error
    with pytest.raises(ValidationError):
        await conversation_manager._history_manager.add_message(session_id, "invalid_role", "Fail")
        
    # Delete history
    deleted = await conversation_manager._history_manager.delete_history(session_id)
    assert deleted is True
    
    count_after = await conversation_manager._history_manager.count_messages(session_id)
    assert count_after == 0
