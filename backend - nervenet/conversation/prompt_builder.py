from typing import List, Dict, Any, Optional
from conversation.models.message import ChatMessage
from conversation.constants import DEFAULT_SYSTEM_PROMPT

class PromptBuilder:
    def build_prompt(
        self,
        system_prompt: Optional[str],
        summary: Optional[str],
        recent_history: List[ChatMessage],
        current_message: str,
        memory: Dict[str, Any],
        privacy_engine: Optional[Any] = None,
        image_blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Construct the prompt components for the Anthropic Claude API.
        
        Combines System Prompt, Summary, and Runtime Memory into the 'system' field,
        and constructs alternating user/assistant dictionaries for the 'messages' list,
        appending the current user message at the end.
        
        Returns:
            Dict[str, Any] with key "system" (str) and "messages" (List[Dict[str, str]]).
        """
        # 1. Base system instruction
        base_system = system_prompt or DEFAULT_SYSTEM_PROMPT
        system_components = [base_system]
        
        # Append Conversation Summary if present
        if summary:
            system_components.append(f"Summary of previous conversation:\n{summary}")
            
        # Append Runtime Memory context if present
        if memory:
            memory_str = "\n".join([f"- {k}: {v}" for k, v in memory.items()])
            system_components.append(f"Session State Variables (Runtime Memory):\n{memory_str}")
            
        combined_system = "\n\n".join(system_components)
        
        # 2. Format recent history
        formatted_messages = []
        for msg in recent_history:
            # Ensure roles align to user/assistant for Claude
            role = "assistant" if msg.role == "assistant" else "user"
            content = msg.content
            if role == "user" and privacy_engine:
                content = privacy_engine.tokenize_text(content)
            formatted_messages.append({
                "role": role,
                "content": content
            })
            
        # 3. Add the active incoming user message
        content_active = current_message
        if privacy_engine:
            content_active = privacy_engine.tokenize_text(content_active)

        if image_blocks:
            content_active_block = [{"type": "text", "text": content_active}] + image_blocks
        else:
            content_active_block = content_active

        formatted_messages.append({
            "role": "user",
            "content": content_active_block
        })
        
        return {
            "system": combined_system,
            "messages": formatted_messages
        }
