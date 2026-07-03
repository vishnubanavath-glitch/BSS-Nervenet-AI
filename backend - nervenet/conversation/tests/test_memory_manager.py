import pytest
from conversation.utils.helpers import generate_uuid

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_memory_management(conversation_manager):
    session_id = generate_uuid()
    await conversation_manager._session_manager.create_session(session_id, "Test Memory")
    
    # Verify initial memory is empty
    mem1 = await conversation_manager._memory_manager.get_memory(session_id)
    assert mem1 == {}
    
    # Update memory variables
    updates = {"user_name": "Alice", "step": 1}
    mem2 = await conversation_manager._memory_manager.update_memory(session_id, updates)
    assert mem2["user_name"] == "Alice"
    assert mem2["step"] == 1
    
    # Verify partial updates merge with existing keys
    more_updates = {"step": 2, "preference": "dark_mode"}
    mem3 = await conversation_manager._memory_manager.update_memory(session_id, more_updates)
    assert mem3["user_name"] == "Alice"
    assert mem3["step"] == 2
    assert mem3["preference"] == "dark_mode"
    
    # Delete memory
    deleted = await conversation_manager._memory_manager.delete_memory(session_id)
    assert deleted is True
    
    # Memory should reset to empty
    mem4 = await conversation_manager._memory_manager.get_memory(session_id)
    assert mem4 == {}
