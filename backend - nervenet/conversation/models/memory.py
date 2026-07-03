from django.db import models
from .session import ChatSession

class ConversationMemory(models.Model):
    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="memory"
    )
    memory_json = models.JSONField(default=dict, blank=True)
    token_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversation_memories"
        verbose_name = "Conversation Memory"
        verbose_name_plural = "Conversation Memories"

    def __str__(self):
        return f"Memory for {self.session.session_id}"
