import uuid
from django.db import models
from django.contrib.auth.models import User

class SessionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"
    DELETED = "DELETED", "Deleted"

class ChatSession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions", null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE
    )

    class Meta:
        db_table = "chat_sessions"
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title or 'Untitled Session'} ({self.session_id})"
