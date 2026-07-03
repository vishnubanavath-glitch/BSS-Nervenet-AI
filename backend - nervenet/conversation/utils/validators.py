import uuid
from conversation.exceptions import ValidationError
from conversation.models.message import MessageRole

def validate_uuid(value: str) -> str:
    """Validate that the string value is a valid UUID."""
    try:
        uuid.UUID(str(value))
        return str(value)
    except (ValueError, AttributeError):
        raise ValidationError(f"Invalid UUID: {value}")

def validate_role(role: str) -> str:
    """Validate that the role is one of the supported MessageRole values."""
    valid_roles = [r.value for r in MessageRole]
    if role not in valid_roles:
        raise ValidationError(f"Invalid message role: {role}. Must be one of {valid_roles}")
    return role
