class ConversationEngineException(Exception):
    """Base exception for all Conversation Engine errors."""
    pass

class SessionNotFoundException(ConversationEngineException):
    """Raised when a chat session is not found."""
    pass

class LLMRequestException(ConversationEngineException):
    """Raised when communication with the language model fails or times out."""
    pass

class ValidationError(ConversationEngineException):
    """Raised when request payload or data validation fails."""
    pass
