from typing import List, Dict, Any
from conversation.models.message import ChatMessage

def format_messages_for_prompt(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    """Format stored database messages for Anthropic's messages API.
    
    Anthropic Claude requires alternating user and assistant messages.
    If a system instruction is in the history, we convert it to user-level instruction blocks,
    because system prompts should ideally be passed in the `system` parameter of messages.create.
    """
    formatted = []
    for msg in messages:
        role = msg.role
        if role == "assistant":
            formatted.append({"role": "assistant", "content": msg.content})
        elif role == "user":
            formatted.append({"role": "user", "content": msg.content})
        elif role == "system":
            formatted.append({"role": "user", "content": f"[System Instruction: {msg.content}]"})
        else:
            # Tool message, map to user or format as user content
            formatted.append({"role": "user", "content": f"[Tool Output: {msg.content}]"})
    return formatted
