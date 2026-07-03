from conversation.models.session import ChatSession
from conversation.models.message import ChatMessage
from typing import List

class TitleGenerator:
    def __init__(self, max_length: int = 50):
        self.max_length = max_length

    async def generate_title(self, session: ChatSession, first_messages: List[ChatMessage], llm_manager) -> str:
        """Generate a concise title once, based on the first few conversation exchanges.
        
        Args:
            session: The ChatSession instance to titling.
            first_messages: List of initial messages in the session.
            llm_manager: The LLMManager instance used to request the title text.
        """
        # If the session already has a title, do not regenerate
        if session.title:
            return session.title
            
        if not first_messages:
            return "New Conversation"
            
        # Format the first round (typically user message + assistant reply)
        exchange_text = "\n".join([f"{m.role}: {m.content}" for m in first_messages[:3]])
        
        prompt = (
            f"Generate a extremely short, concise title (max {self.max_length} characters) "
            "for a conversation starting with this exchange. "
            "Do not include quotes, punctuation, prefixes or explanations. Return ONLY the title text.\n\n"
            f"Exchange:\n{exchange_text}\n\n"
            "Title:"
        )
        
        # Query the LLM
        # We wrap it in a mock-compatible prompt format
        payload = {
            "system": "You are a conversation titling utility.",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = await llm_manager.generate_response(payload)
        title_text = response.content.strip()
        
        # Clean quotes
        if title_text.startswith('"') and title_text.endswith('"'):
            title_text = title_text[1:-1]
        if title_text.startswith("'") and title_text.endswith("'"):
            title_text = title_text[1:-1]
            
        title_text = title_text.strip()
        
        if len(title_text) > self.max_length:
            title_text = title_text[:self.max_length].rstrip() + "..."
            
        return title_text
