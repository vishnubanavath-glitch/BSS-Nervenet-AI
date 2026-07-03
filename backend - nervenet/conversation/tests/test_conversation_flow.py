import pytest
import unittest.mock
from conversation.utils.helpers import generate_uuid
from conversation.models.session import SessionStatus
from conversation.models.message import ChatMessage
from conversation.models.memory import ConversationMemory
from conversation.models.summary import ConversationSummary

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_full_conversation_lifecycle(conversation_manager):
    session_id = generate_uuid()
    
    # 1. Initialize session and verify empty states are registered
    session = await conversation_manager.initialize_session(session_id, title=None)
    assert str(session.session_id) == session_id
    assert session.title is None
    
    memory_record = await ConversationMemory.objects.aget(session_id=session_id)
    assert memory_record.memory_json == {}
    
    summary_record = await ConversationSummary.objects.aget(session_id=session_id)
    assert summary_record.summary == ""

    # 2. Process message 1 (User sends "Hello")
    # This should store the user message, retrieve response, update memory, and trigger auto-titling.
    res1 = await conversation_manager.process_message(
        session_id=session_id,
        content="Hello!",
        role="user",
        memory_updates={"user_first_name": "Bob"}
    )
    
    assert res1.session_id == session_id
    assert "nervenet ai server is busy try after some time" in res1.response_content
    assert res1.memory == {"user_first_name": "Bob"}
    
    # Verify title auto-generation ran
    session = await conversation_manager._session_manager.load_session(session_id)
    assert session.title == "Generated Title"

    # Verify history counts (User msg + Assistant reply)
    count = await conversation_manager._history_manager.count_messages(session_id)
    assert count == 2

    # 3. Send message 2 and trigger summarization threshold
    # We mock should_summarize to return True to simulate threshold breach
    # We mock PRESERVE_RECENT_MESSAGES_COUNT to 1 to allow summarizing with 3 total messages
    with unittest.mock.patch("conversation.token_manager.TokenManager.should_summarize", return_value=True), \
         unittest.mock.patch("conversation.summary_manager.PRESERVE_RECENT_MESSAGES_COUNT", 1):
        res2 = await conversation_manager.process_message(
            session_id=session_id,
            content="Can you summarize?",
            role="user"
        )
        
        # Verify summary was created and updated in database
        summary_record = await ConversationSummary.objects.aget(session_id=session_id)
        assert summary_record.summary == "This is a consolidated summary of the previous chat history."
        assert summary_record.last_processed_message_id is not None
        
    # 4. Perform session deletion
    deleted = await conversation_manager._session_manager.delete_session(session_id)
    assert deleted is True
    
    # 5. Verify database cascade deletions occurred for all related data models
    with pytest.raises(ChatMessage.DoesNotExist):
        await ChatMessage.objects.filter(session_id=session_id).aget()
        
    with pytest.raises(ConversationMemory.DoesNotExist):
        await ConversationMemory.objects.aget(session_id=session_id)
        
    with pytest.raises(ConversationSummary.DoesNotExist):
        await ConversationSummary.objects.aget(session_id=session_id)
