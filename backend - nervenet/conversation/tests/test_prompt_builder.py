import pytest
from conversation.prompt_builder import PromptBuilder
from conversation.models.message import ChatMessage
from conversation.models.session import ChatSession
from conversation.utils.helpers import generate_uuid

def test_prompt_builder():
    builder = PromptBuilder()
    session = ChatSession(session_id=generate_uuid(), title="Test Session")
    
    # Setup mock message history
    m1 = ChatMessage(message_id=generate_uuid(), session=session, role="user", content="Hello assistant")
    m2 = ChatMessage(message_id=generate_uuid(), session=session, role="assistant", content="Hello human")
    recent_history = [m1, m2]
    
    system_prompt = "You are a specialized math solver."
    summary = "User said hello."
    memory = {"preferred_subject": "Algebra"}
    current_message = "Solve 2+2"
    
    result = builder.build_prompt(
        system_prompt=system_prompt,
        summary=summary,
        recent_history=recent_history,
        current_message=current_message,
        memory=memory
    )
    
    assert "system" in result
    assert "messages" in result
    
    # Assert system prompt incorporates all aspects
    system_blocks = result["system"]
    assert len(system_blocks) == 3
    assert system_blocks[0] == {"type": "text", "text": "You are a specialized math solver."}
    assert system_blocks[1] == {"type": "text", "text": "Summary of previous conversation:\nUser said hello."}
    assert system_blocks[2] == {"type": "text", "text": "Session State Variables (Runtime Memory):\n- preferred_subject: Algebra"}
    
    # Assert messages follow chronological Claude parameters
    msg_list = result["messages"]
    assert len(msg_list) == 3
    assert msg_list[0] == {"role": "user", "content": "Hello assistant"}
    assert msg_list[1] == {"role": "assistant", "content": "Hello human"}
    assert msg_list[2] == {"role": "user", "content": "Solve 2+2"}
