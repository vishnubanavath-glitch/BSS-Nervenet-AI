from django.contrib import admin
from conversation.models.session import ChatSession
from conversation.models.message import ChatMessage
from conversation.models.memory import ConversationMemory
from conversation.models.summary import ConversationSummary

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("role", "content", "prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost", "created_at")
    readonly_fields = ("created_at",)
    can_delete = True
    ordering = ("created_at",)

class ConversationMemoryInline(admin.StackedInline):
    model = ConversationMemory
    extra = 0
    readonly_fields = ("token_count", "updated_at")

class ConversationSummaryInline(admin.StackedInline):
    model = ConversationSummary
    extra = 0
    readonly_fields = ("token_count", "generated_at")

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "title", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("session_id", "title")
    inlines = [ChatMessageInline, ConversationMemoryInline, ConversationSummaryInline]

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("message_id", "session_link", "role", "content_preview", "prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("session__session_id", "content")
    readonly_fields = ("created_at",)

    def session_link(self, obj):
        return f"{obj.session.title or 'Untitled'} ({obj.session.session_id})"
    session_link.short_description = "Session"

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Content"

@admin.register(ConversationMemory)
class ConversationMemoryAdmin(admin.ModelAdmin):
    list_display = ("session", "updated_at")
    search_fields = ("session__session_id",)

@admin.register(ConversationSummary)
class ConversationSummaryAdmin(admin.ModelAdmin):
    list_display = ("session", "generated_at", "last_processed_message_id")
    search_fields = ("session__session_id", "summary")
