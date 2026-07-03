import uuid
from django.db import models
from django.contrib.auth.models import User
from .message import ChatMessage

class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attachments")
    message = models.ForeignKey(ChatMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    file = models.FileField(upload_to="attachments/")
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size = models.IntegerField()
    extracted_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attachments"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.filename} ({self.id})"
