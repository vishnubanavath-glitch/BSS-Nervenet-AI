import uuid
from django.db import models
from .session import ChatSession

class MessageRole(models.TextChoices):
    SYSTEM = "system", "System"
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    TOOL = "tool", "Tool"

class ChatMessage(models.Model):
    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    role = models.CharField(
        max_length=20,
        choices=MessageRole.choices
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Token tracking columns (usage)
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        db_table = "chat_messages"
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}..."
