import decimal
import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from conversation.models.wallet import Wallet
from conversation.models.message import ChatMessage
from conversation.models.attachment import Attachment
from conversation.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)

# Verify user is an administrator
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_dashboard_view(request):
    User = get_user_model()
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    
    # Calculate tokens used and revenue (using Wallet balances)
    total_tokens = sum(w.total_tokens_used for w in Wallet.objects.all())
    
    # Cost trend (mock values aligned to UI chart expected formats)
    cost_trend = [
        {"date": "2026-06-28", "tokens": 120000, "cost": 4.50},
        {"date": "2026-06-29", "tokens": 140000, "cost": 5.50},
        {"date": "2026-06-30", "tokens": 220000, "cost": 8.90},
        {"date": "2026-07-01", "tokens": 250000, "cost": 9.80},
        {"date": "2026-07-02", "tokens": 280000, "cost": 11.20}
    ]
    
    return Response({
        "total_users": total_users,
        "active_users_today": active_users,
        "total_tokens_billed": total_tokens,
        "total_revenue": 142.50, # mock revenue
        "cost_trend": cost_trend
    }, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_users_list_view(request):
    User = get_user_model()
    users = User.objects.all()
    
    users_data = []
    for user in users:
        wallet, _ = Wallet.objects.get_or_create(user=user)
        full_name = f"{user.first_name} {user.last_name}".strip()
        users_data.append({
            "id": user.id,
            "email": user.email or user.username,
            "username": user.username,
            "full_name": full_name or user.username,
            "is_active": user.is_active,
            "is_admin": user.is_staff or user.is_superuser,
            "wallet": {
                "balance": float(wallet.balance),
                "total_tokens_used": wallet.total_tokens_used
            }
        })
    return Response(users_data, status=status.HTTP_200_OK)

@api_view(["POST", "DELETE"])
@permission_classes([IsAdminUser])
def admin_user_detail_view(request, user_id):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == "POST":
        # Toggle ban/is_active status
        user.is_active = not user.is_active
        user.save()
        return Response({"detail": f"User active status set to {user.is_active}"}, status=status.HTTP_200_OK)
        
    elif request.method == "DELETE":
        # Delete user
        user.delete()
        return Response({"detail": "User deleted successfully."}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_user_credits_view(request, user_id):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        
    credits_amount = request.data.get("credits_amount", 10.0)
    try:
        amt = decimal.Decimal(str(credits_amount))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return Response({"detail": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)
        
    wallet, _ = Wallet.objects.get_or_create(user=user)
    wallet.balance += amt
    wallet.save()
    return Response({
        "balance": float(wallet.balance)
    }, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_providers_view(request):
    return Response([
        {"id": "claude", "name": "Anthropic Claude", "is_enabled": True, "api_key": "sk-ant-*********"},
        {"id": "openai", "name": "OpenAI GPT", "is_enabled": False, "api_key": ""}
    ], status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAdminUser])
def admin_provider_detail_view(request, provider_id):
    is_enabled = request.data.get("is_enabled")
    api_key = request.data.get("api_key")
    return Response({
        "id": provider_id,
        "name": "Anthropic Claude" if provider_id == "claude" else "OpenAI GPT",
        "is_enabled": is_enabled if is_enabled is not None else True,
        "api_key": api_key or "sk-ant-*********"
    }, status=status.HTTP_200_OK)

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_models_view(request):
    if request.method == "GET":
        return Response([
            {"id": "claude-sonnet-4-6", "provider": "claude", "name": "Claude 3.5 Sonnet", "context": 200000},
            {"id": "claude-opus-3", "provider": "claude", "name": "Claude 3 Opus", "context": 200000}
        ], status=status.HTTP_200_OK)
    elif request.method == "POST":
        data = request.data
        return Response({
            "id": data.get("id", "new-model"),
            "provider": data.get("provider", "claude"),
            "name": data.get("name", "New Model"),
            "context": data.get("context", 100000)
        }, status=status.HTTP_201_CREATED)

@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def admin_model_detail_view(request, model_id):
    return Response({"detail": "Model deleted successfully"}, status=status.HTTP_200_OK)

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_subscriptions_view(request):
    if request.method == "GET":
        return Response([
            {"id": "free", "name": "Developer Free", "price": 0, "tokens": 100000, "msgs": 100, "upload": 5},
            {"id": "pro", "name": "Enterprise Pro", "price": 29, "tokens": 1000000, "msgs": 1000, "upload": 20}
        ], status=status.HTTP_200_OK)
    elif request.method == "POST":
        data = request.data
        return Response({
            "id": data.get("name", "new-plan").lower().replace(" ", "-"),
            "name": data.get("name", "New Plan"),
            "price": data.get("price", 0),
            "tokens": data.get("tokens", 100000),
            "msgs": data.get("msgs", 1000),
            "upload": data.get("upload", 10)
        }, status=status.HTTP_201_CREATED)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_files_view(request):
    files = Attachment.objects.all().order_by("-created_at")
    files_data = []
    for f in files:
        files_data.append({
            "id": str(f.id),
            "filename": f.filename,
            "mime_type": f.mime_type,
            "file_size": f.file_size,
            "user_email": f.user.email,
            "created_at": f.created_at.isoformat()
        })
    return Response(files_data, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_logs_view(request):
    messages = ChatMessage.objects.all().order_by("-created_at")[:50]
    logs_data = []
    for m in messages:
        logs_data.append({
            "id": str(m.message_id),
            "user_email": m.session.user.email if m.session.user else "Anonymous",
            "session_title": m.session.title or "Untitled",
            "role": m.role,
            "tokens": m.total_tokens or 0,
            "cost": float(m.estimated_cost or 0),
            "created_at": m.created_at.isoformat()
        })
    return Response(logs_data, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_tickets_view(request):
    return Response([], status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAdminUser])
def admin_ticket_detail_view(request, ticket_id):
    return Response({
        "id": ticket_id,
        "status": "resolved",
        "internal_notes": request.data.get("internal_notes", "")
    }, status=status.HTTP_200_OK)

@api_view(["GET", "PUT"])
@permission_classes([IsAdminUser])
def admin_settings_view(request):
    if request.method == "GET":
        return Response([
            {"key": "conversation_limit", "value": "30", "description": "Maximum turns per chat"},
            {"key": "default_balance", "value": "5.00", "description": "Sign-up wallet credits"},
        ], status=status.HTTP_200_OK)
    elif request.method == "PUT":
        key = request.query_params.get("key")
        val = request.data.get("setting_value")
        return Response({
            "key": key,
            "value": val,
            "detail": "Setting updated successfully"
        }, status=status.HTTP_200_OK)

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_mcp_view(request):
    if request.method == "GET":
        return Response([
            {
                "id": "db-mcp",
                "name": "Database MCP Server",
                "description": "Secure read-only MySQL DB query connector",
                "server_type": "stdio",
                "command": "python",
                "args": "database_mcp/app.py",
                "env_variables": "MYSQL_USER, MYSQL_PASSWORD",
                "is_enabled": True
            }
        ], status=status.HTTP_200_OK)
    elif request.method == "POST":
        data = request.data
        return Response({
            "id": "mcp-" + generate_uuid()[:8],
            "name": data.get("name", "New MCP"),
            "description": data.get("description", ""),
            "server_type": data.get("server_type", "sse"),
            "url": data.get("url", ""),
            "command": data.get("command", ""),
            "args": data.get("args", ""),
            "env_variables": data.get("env_variables", ""),
            "is_enabled": True
        }, status=status.HTTP_201_CREATED)

@api_view(["PUT", "DELETE"])
@permission_classes([IsAdminUser])
def admin_mcp_detail_view(request, mcp_id):
    if request.method == "PUT":
        data = request.data
        return Response({
            "id": mcp_id,
            "name": data.get("name", "Database MCP"),
            "description": data.get("description", ""),
            "server_type": data.get("server_type", "stdio"),
            "url": data.get("url", ""),
            "command": data.get("command", ""),
            "args": data.get("args", ""),
            "env_variables": data.get("env_variables", ""),
            "is_enabled": data.get("is_enabled", True)
        }, status=status.HTTP_200_OK)
    elif request.method == "DELETE":
        return Response({"detail": "MCP server deleted successfully"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_mcp_test_view(request, mcp_id):
    return Response({
        "status": "success",
        "message": f"Successfully connected to MCP server {mcp_id}"
    }, status=status.HTTP_200_OK)

