import pytest
from conversation.llm_manager import LLMManager
from .conftest import TestMockLLMProvider as MockLLMProvider

@pytest.mark.asyncio
async def test_mock_llm_provider():
    provider = MockLLMProvider()
    manager = LLMManager(provider)
    
    prompt = {
        "system": "System instructions",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
    
    # Verify standard response generation
    response = await manager.generate_response(prompt)
    assert "nervenet ai server is busy try after some time" in response.content
    assert response.prompt_tokens > 0
    assert response.completion_tokens > 0
    assert response.total_tokens == response.prompt_tokens + response.completion_tokens
    
    # Verify streaming generator output
    chunks = []
    async for chunk in manager.generate_response_stream(prompt):
        chunks.append(chunk)
        
    full_text = "".join(chunks).strip()
    assert "nervenet ai server is busy try after some time" in full_text

def test_prepare_caching_params():
    from conversation.llm_manager import prepare_caching_params
    
    # Test system prompt string caching
    system_str = "Static core prompt"
    sys_blocks, tools_blocks = prepare_caching_params(system_str, None)
    
    assert sys_blocks == [
        {
            "type": "text",
            "text": "Static core prompt",
            "cache_control": {"type": "ephemeral"}
        }
    ]
    assert tools_blocks is None
    
    # Test system prompt list caching
    system_list = [
        {"type": "text", "text": "Base system instruction"},
        {"type": "text", "text": "Dynamic summary"}
    ]
    sys_blocks, _ = prepare_caching_params(system_list, None)
    assert len(sys_blocks) == 2
    # Caching ONLY the first static block
    assert sys_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in sys_blocks[1]
    
    # Test tools caching
    tools_list = [
        {"name": "tool_1", "description": "Desc 1", "input_schema": {}},
        {"name": "tool_2", "description": "Desc 2", "input_schema": {}}
    ]
    _, tools_blocks = prepare_caching_params(None, tools_list)
    assert len(tools_blocks) == 2
    assert "cache_control" not in tools_blocks[0]
    # Caching the last tool to cache all tool definitions
    assert tools_blocks[1]["cache_control"] == {"type": "ephemeral"}

