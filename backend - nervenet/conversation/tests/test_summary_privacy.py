import pytest
import unittest.mock
from conversation.utils.helpers import generate_uuid
from conversation.models.summary import ConversationSummary
from conversation.models.message import ChatMessage

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_summary_privacy_leak_plugged(conversation_manager):
    session_id = generate_uuid()
    
    # 1. Initialize session
    await conversation_manager.initialize_session(session_id, title=None)
    
    # 2. Add some chat history containing raw PII
    raw_phone = "9876543210"
    raw_uid = "5901234"
    
    # Send a message with phone and uid.
    # The message is processed and stored in history.
    await conversation_manager.process_message(
        session_id=session_id,
        content=f"Hello, my phone is {raw_phone} and customer id is {raw_uid}.",
        role="user"
    )
    
    # Verify database contains the raw user message (raw PII is stored securely on server side DB)
    messages = await conversation_manager._history_manager.get_complete_history(session_id)
    assert len(messages) >= 2
    user_msg = [m for m in messages if m.role == "user"][0]
    assert raw_phone in user_msg.content
    assert raw_uid in user_msg.content

    # Capture prompt sent to the LLM during summarization
    captured_prompts = []
    async def mock_generate_response(prompt_data):
        # prompt_data can be str or dict, get prompt text
        if isinstance(prompt_data, str):
            captured_prompts.append(prompt_data)
        else:
            messages = prompt_data.get("messages", [])
            captured_prompts.append(str(messages))
            
        from conversation.llm_manager import LLMResponse
        from anthropic.types import TextBlock
        content = "This is a summary of the conversation."
        content_blocks = [TextBlock(text=content, type="text")]
        return LLMResponse(content, 10, 10, content_blocks)

    original_generate_response = conversation_manager._llm_manager.generate_response
    conversation_manager._llm_manager.generate_response = mock_generate_response
    
    try:
        # Load privacy state from memory
        memory = await conversation_manager._memory_manager.get_memory(session_id)
        from conversation.privacy_engine import PrivacyEngine
        privacy_engine = PrivacyEngine()
        privacy_engine.load_state(memory.get("_privacy_state"))
        
        # Verify the privacy engine mapping is established
        assert raw_phone in privacy_engine.value_to_token
        assert raw_uid in privacy_engine.value_to_token
        
        # Trigger summarization with the privacy engine
        with unittest.mock.patch("conversation.summary_manager.PRESERVE_RECENT_MESSAGES_COUNT", 1):
            await conversation_manager._summary_manager.summarize_history(
                session_id=session_id,
                llm_manager=conversation_manager._llm_manager,
                privacy_engine=privacy_engine
            )
        
        # Assertions
        assert len(captured_prompts) == 1
        summarizer_prompt = captured_prompts[0]
        
        # 1. Raw PII must NOT be leaked to the LLM
        assert raw_phone not in summarizer_prompt
        assert raw_uid not in summarizer_prompt
        
        # 2. Masked tokens MUST be sent instead
        phone_token = privacy_engine.value_to_token[raw_phone]
        uid_token = privacy_engine.value_to_token[raw_uid]
        assert phone_token in summarizer_prompt
        assert uid_token in summarizer_prompt
        
    finally:
        # Restore original generate_response
        conversation_manager._llm_manager.generate_response = original_generate_response
