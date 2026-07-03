import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional, Union
from anthropic import AsyncAnthropic, APIError
from conversation.exceptions import LLMRequestException
from conversation.constants import LLM_MODEL

logger = logging.getLogger(__name__)

class LLMResponse:
    """Unified response object to track LLM text output and token metrics."""
    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int, content_blocks: Optional[List[Any]] = None):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.content_blocks = content_blocks or []

class LLMProvider(ABC):
    """Abstract Base Class defining the contract for LLM communication."""
    @abstractmethod
    async def generate(
        self,
        system: Optional[str],
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def generate_stream(
        self,
        system: Optional[str],
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        pass

_anthropic_client: Optional[AsyncAnthropic] = None

class AnthropicLLMProvider(LLMProvider):
    """Real client implementation utilizing Claude via anthropic's Async client."""
    def __init__(self, api_key: Optional[str] = None):
        global _anthropic_client
        if _anthropic_client is None:
            # Reads from ANTHROPIC_API_KEY environment variable if api_key is None
            _anthropic_client = AsyncAnthropic(api_key=api_key)
        self.client = _anthropic_client

    async def generate(
        self,
        system: Optional[str],
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.5,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        retries = 3
        delay = 1.0
        for attempt in range(retries):
            try:
                params = {
                    "model": LLM_MODEL,
                    "max_tokens": max_tokens,
                    "system": system or "",
                    "messages": messages
                }
                if tools:
                    params["tools"] = tools

                response = await self.client.messages.create(**params)
                
                content_blocks = response.content
                # Concatenate all TextBlock texts
                text_content = "".join([
                    block.text for block in content_blocks 
                    if hasattr(block, "text") and block.text
                ])
                
                prompt_tokens = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens
                return LLMResponse(text_content, prompt_tokens, completion_tokens, content_blocks)
            except APIError as e:
                logger.warning(f"Anthropic API error on attempt {attempt+1}: {e}")
                if attempt == retries - 1:
                    raise LLMRequestException(f"Failed to communicate with Claude API after retries: {e}")
                await asyncio.sleep(delay)
                delay *= 2
            except Exception as e:
                logger.error(f"Unexpected exception calling Claude: {e}")
                raise LLMRequestException(f"Error calling Claude: {e}")

    async def generate_stream(
        self,
        system: Optional[str],
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        try:
            async with self.client.messages.stream(
                model=LLM_MODEL,
                max_tokens=max_tokens,
                system=system or "",
                messages=messages
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Streaming exception calling Claude: {e}")
            raise LLMRequestException(f"Streaming error from Claude: {e}")

class LLMManager:
    """Manager wrapping the LLM provider to format standard payloads."""
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def generate_response(
        self,
        prompt_data: Union[str, Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> LLMResponse:
        """Forward prompt details to the underlying LLM provider."""
        if isinstance(prompt_data, str):
            system = None
            messages = [{"role": "user", "content": prompt_data}]
        else:
            system = prompt_data.get("system")
            messages = prompt_data.get("messages", [])
        return await self._provider.generate(system, messages, max_tokens, temperature)

    async def generate_response_stream(
        self,
        prompt_data: Union[str, Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Stream chunks from the underlying LLM provider."""
        if isinstance(prompt_data, str):
            system = None
            messages = [{"role": "user", "content": prompt_data}]
        else:
            system = prompt_data.get("system")
            messages = prompt_data.get("messages", [])
        async for chunk in self._provider.generate_stream(system, messages, max_tokens, temperature):
            yield chunk
