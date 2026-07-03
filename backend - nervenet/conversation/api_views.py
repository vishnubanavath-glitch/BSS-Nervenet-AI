import decimal
import os
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from conversation.models.session import ChatSession, SessionStatus
from conversation.models.message import ChatMessage
from conversation.models.wallet import Wallet
from conversation.models.attachment import Attachment
from conversation.controller import get_conversation_manager
from conversation.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)

# --- Wallet & Payments ---
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_balance_view(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return Response({
        "balance": float(wallet.balance),
        "total_tokens_used": wallet.total_tokens_used
    }, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_add_funds_view(request):
    amount = request.data.get("amount", 10.0)
    try:
        amt = decimal.Decimal(str(amount))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return Response({"detail": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)
        
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    wallet.balance += amt
    wallet.save()
    return Response({
        "balance": float(wallet.balance)
    }, status=status.HTTP_200_OK)

# --- Models list ---
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def models_list_view(request):
    return Response([
        {
            "model_id": "claude-sonnet-4-6",
            "display_name": "Claude 3.5 Sonnet (v2)",
            "provider": "claude",
            "context_window": 200000
        },
        {
            "model_id": "claude-opus-3",
            "display_name": "Claude 3 Opus",
            "provider": "claude",
            "context_window": 200000
        },
        {
            "model_id": "claude-haiku-3-5",
            "display_name": "Claude 3.5 Haiku",
            "provider": "claude",
            "context_window": 200000
        }
    ], status=status.HTTP_200_OK)

# --- Files upload ---
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def file_upload_view(request):
    file_obj = request.FILES.get("file")
    if not file_obj:
        return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        
    attachment = Attachment.objects.create(
        user=request.user,
        file=file_obj,
        filename=file_obj.name,
        mime_type=file_obj.content_type or "application/octet-stream",
        file_size=file_obj.size,
    )
    
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext in [".txt", ".csv", ".log", ".json", ".xml", ".html", ".md"]:
        try:
            file_obj.seek(0)
            text = file_obj.read().decode("utf-8", errors="ignore")
            attachment.extracted_text = text
            attachment.save()
        except Exception as e:
            logger.warning(f"Failed to extract text from file: {e}")
            
    return Response({
        "id": str(attachment.id),
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "file_size": attachment.file_size
    }, status=status.HTTP_201_CREATED)

# --- Conversations/Sessions ---
def serialize_conversation(session):
    return {
        "id": str(session.session_id),
        "title": session.title or "New Chat",
        "is_archived": session.status == SessionStatus.ARCHIVED,
        "is_pinned": session.is_pinned,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat()
    }

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def conversations_list_create_view(request):
    if request.method == "GET":
        sessions = ChatSession.objects.filter(
            user=request.user, 
            status__in=[SessionStatus.ACTIVE, SessionStatus.ARCHIVED]
        ).order_by("-is_pinned", "-updated_at")
        
        return Response([serialize_conversation(s) for s in sessions], status=status.HTTP_200_OK)
        
    elif request.method == "POST":
        title = request.data.get("title", "")
        if title == "New Chat":
            title = ""
        session_id = generate_uuid()
        
        # We manually initialize session in our model, associated with authenticated user
        session = ChatSession.objects.create(
            session_id=session_id,
            user=request.user,
            title=title,
            status=SessionStatus.ACTIVE
        )
        
        # Initialize memory & summaries inside the manager flow
        manager = get_conversation_manager()
        # Initialize memory model entries
        from conversation.models.memory import ConversationMemory
        from conversation.models.summary import ConversationSummary
        ConversationMemory.objects.get_or_create(session=session, defaults={"memory_json": {}})
        ConversationSummary.objects.get_or_create(session=session, defaults={"summary": "", "last_processed_message_id": None})
        
        return Response(serialize_conversation(session), status=status.HTTP_201_CREATED)

@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def conversation_detail_view(request, conversation_id):
    try:
        session = ChatSession.objects.get(session_id=conversation_id, user=request.user)
    except ChatSession.DoesNotExist:
        return Response({"detail": "Conversation not found."}, status=status.HTTP_404_BAD_REQUEST)
        
    if request.method == "GET":
        from conversation.models.memory import ConversationMemory
        from conversation.models.summary import ConversationSummary
        try:
            mem = ConversationMemory.objects.get(session=session)
            memory_dict = mem.memory_json
        except ConversationMemory.DoesNotExist:
            memory_dict = {}
        try:
            summ = ConversationSummary.objects.get(session=session)
            summary_text = summ.summary
        except ConversationSummary.DoesNotExist:
            summary_text = ""
        
        data = serialize_conversation(session)
        data["memory"] = memory_dict
        data["summary"] = summary_text
        return Response(data, status=status.HTTP_200_OK)
        
    elif request.method == "PUT":
        title = request.data.get("title")
        is_pinned = request.data.get("is_pinned")
        is_archived = request.data.get("is_archived")
        
        if title is not None:
            session.title = title
        if is_pinned is not None:
            session.is_pinned = bool(is_pinned)
        if is_archived is not None:
            if bool(is_archived):
                session.status = SessionStatus.ARCHIVED
            else:
                session.status = SessionStatus.ACTIVE
                
        session.save()
        return Response(serialize_conversation(session), status=status.HTTP_200_OK)
        
    elif request.method == "DELETE":
        session.status = SessionStatus.DELETED
        session.save()
        return Response({"detail": "Conversation deleted successfully"}, status=status.HTTP_200_OK)

# --- Conversation Messages ---
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_messages_view(request, conversation_id):
    try:
        session = ChatSession.objects.get(session_id=conversation_id, user=request.user)
    except ChatSession.DoesNotExist:
        return Response({"detail": "Conversation not found."}, status=status.HTTP_404_BAD_REQUEST)
        
    messages = ChatMessage.objects.filter(session=session).order_by("created_at")
    
    serialized_messages = []
    # Instantiate PrivacyEngine to detokenize assistant messages
    from conversation.privacy_engine import PrivacyEngine
    from conversation.models.memory import ConversationMemory
    
    privacy_engine = PrivacyEngine()
    try:
        mem = ConversationMemory.objects.get(session_id=conversation_id)
        privacy_engine.load_state(mem.memory_json.get("_privacy_state", {}))
    except ConversationMemory.DoesNotExist:
        pass

    for msg in messages:
        # Detokenize content for display if Assistant
        content_to_show = msg.content
        if msg.role == "assistant":
            content_to_show = privacy_engine.detokenize_text(msg.content)
            
        serialized_messages.append({
            "id": str(msg.message_id),
            "conversation_id": str(msg.session_id),
            "role": msg.role,
            "content": content_to_show,
            "created_at": msg.created_at.isoformat(),
            "metadata": {
                "model": "claude-3-5-sonnet",
                "telemetry": {
                    "prompt_tokens": msg.prompt_tokens or 0,
                    "completion_tokens": msg.completion_tokens or 0,
                    "cache_read_tokens": 0,
                    "cost": float(msg.estimated_cost or 0)
                }
            },
            "attachments": [
                {
                    "id": str(att.id),
                    "filename": att.filename,
                    "mime_type": att.mime_type,
                    "file_size": att.file_size
                }
                for att in msg.attachments.all()
            ]
        })
        
    return Response(serialized_messages, status=status.HTTP_200_OK)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_message_view(request, conversation_id, message_id):
    try:
        session = ChatSession.objects.get(session_id=conversation_id, user=request.user)
    except ChatSession.DoesNotExist:
        return Response({"detail": "Conversation not found."}, status=status.HTTP_404_BAD_REQUEST)
        
    try:
        msg = ChatMessage.objects.get(message_id=message_id, session=session)
        msg.delete()
        return Response({"detail": "Message deleted successfully"}, status=status.HTTP_200_OK)
    except ChatMessage.DoesNotExist:
        return Response({"detail": "Message not found"}, status=status.HTTP_404_BAD_REQUEST)
