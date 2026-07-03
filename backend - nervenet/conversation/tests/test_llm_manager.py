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
