import pytest
import asyncio
from typing import Optional, List, Dict, AsyncGenerator, Any
from conversation.manager import ConversationManager
from conversation.session_manager import SessionManager
from conversation.history_manager import HistoryManager
from conversation.memory_manager import MemoryManager
from conversation.summary_manager import SummaryManager
from conversation.prompt_builder import PromptBuilder
from conversation.llm_manager import LLMManager, LLMProvider, LLMResponse
from conversation.token_manager import TokenManager
from conversation.title_generator import TitleGenerator
from conversation.storage import (
    DjangoSessionStore,
    DjangoHistoryStore,
    DjangoMemoryStore,
    DjangoSummaryStore
)

class TestMockLLMProvider(LLMProvider):
    """Local mock LLM provider for unit and integration testing."""
    async def generate(
        self,
        system: Optional[str],
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        await asyncio.sleep(0.01)
        last_msg = messages[-1]["content"] if messages else ""
        
        # If it's a string, process normally, otherwise handle list of content blocks
        if not isinstance(last_msg, str):
            last_msg = str(last_msg)

        if "summarize" in last_msg.lower() or "summary" in last_msg.lower():
            content = "This is a consolidated summary of the previous chat history."
        elif "title" in last_msg.lower():
            content = "Generated Title"
        else:
            content = "nervenet ai server is busy try after some time"
            
        prompt_tokens = len(str(system or "") + str(messages)) // 4
        completion_tokens = len(content) // 4
        
        from anthropic.types import TextBlock
        content_blocks = [TextBlock(text=content, type="text")]
        return LLMResponse(content, prompt_tokens, completion_tokens, content_blocks)

    async def generate_stream(
        self,
        system: Optional[str],
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        content = "nervenet ai server is busy try after some time"
        for word in content.split():
            await asyncio.sleep(0.01)
            yield word + " "

@pytest.fixture
def conversation_manager() -> ConversationManager:
    """Fixture returning a pre-wired ConversationManager utilizing the TestMockLLMProvider."""
    provider = TestMockLLMProvider()
    llm_mgr = LLMManager(provider)
    session_repo = DjangoSessionStore()
    history_repo = DjangoHistoryStore()
    memory_repo = DjangoMemoryStore()
    summary_repo = DjangoSummaryStore()
    
    return ConversationManager(
        session_manager=SessionManager(session_repo),
        history_manager=HistoryManager(history_repo),
        memory_manager=MemoryManager(memory_repo),
        summary_manager=SummaryManager(summary_repo, history_repo),
        prompt_builder=PromptBuilder(),
        llm_manager=llm_mgr,
        token_manager=TokenManager(),
        title_generator=TitleGenerator()
    )
