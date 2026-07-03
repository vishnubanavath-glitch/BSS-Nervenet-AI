from django.db import models
from django.contrib.auth.models import User
import uuid

class ProviderSettings(models.Model):
    id = models.CharField(max_length=50, primary_key=True)  # 'claude', 'openai'
    name = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    api_key = models.CharField(max_length=500, blank=True, default="")
    api_key_encrypted = models.BooleanField(default=False)
    avg_latency_ms = models.FloatField(default=0.0)
    request_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'provider_settings'

    def __str__(self):
        return self.name

class LLMModel(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    provider = models.CharField(max_length=50)  # 'claude', 'openai'
    name = models.CharField(max_length=100)
    context = models.IntegerField(default=100000)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'llm_models'

    def __str__(self):
        return self.name

class BillingPlan(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=100)
    price = models.FloatField(default=0.0)
    tokens = models.IntegerField(default=100000)
    msgs = models.IntegerField(default=1000)
    upload = models.IntegerField(default=10)

    class Meta:
        db_table = 'billing_plans'

    def __str__(self):
        return self.name

class AppSetting(models.Model):
    key = models.CharField(max_length=100, primary_key=True)
    value = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = 'app_settings'

    def __str__(self):
        return self.key

def generate_short_id():
    return str(uuid.uuid4())[:8]

class SupportTicket(models.Model):
    id = models.CharField(max_length=50, primary_key=True, default=generate_short_id)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=50, default="open")  # 'open', 'resolved', etc.
    internal_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_tickets'

    def __str__(self):
        return f"{self.id} - {self.title}"

class MCPServer(models.Model):
    id = models.CharField(max_length=50, primary_key=True, default=generate_short_id)

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    server_type = models.CharField(max_length=50, default="sse")  # 'stdio', 'sse'
    url = models.CharField(max_length=500, blank=True, default="")
    command = models.CharField(max_length=100, blank=True, default="")
    args = models.CharField(max_length=500, blank=True, default="")
    env_variables = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'mcp_servers'

    def __str__(self):
        return self.name
