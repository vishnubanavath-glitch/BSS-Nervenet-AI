from django.db import models
from .session import ChatSession

class ConversationSummary(models.Model):
    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="summary"
    )
    summary = models.TextField(blank=True, default="")
    token_count = models.IntegerField(default=0)
    generated_at = models.DateTimeField(auto_now=True)
    last_processed_message_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "conversation_summaries"
        verbose_name = "Conversation Summary"
        verbose_name_plural = "Conversation Summaries"

    def __str__(self):
        return f"Summary for {self.session.session_id}"
