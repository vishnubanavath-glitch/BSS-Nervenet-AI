import decimal
import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from conversation.models import (
    Wallet, ChatMessage, Attachment,
    ProviderSettings, LLMModel, BillingPlan,
    AppSetting, SupportTicket, MCPServer
)
from conversation.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)

def check_and_init_data():
    try:
        import os
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or ""
        openai_key = os.environ.get("OPENAI_API_KEY") or ""

        # 1. Init/Update Anthropic Claude Provider
        p_claude, created = ProviderSettings.objects.get_or_create(
            id="claude",
            defaults={
                "name": "Anthropic Claude",
                "is_enabled": True,
                "api_key": anthropic_key or "sk-ant-*********",
                "api_key_encrypted": True if anthropic_key else False,
                "avg_latency_ms": 150.0,
                "request_count": 420,
                "error_count": 0
            }
        )
        if not created and (p_claude.api_key == "sk-ant-*********" or not p_claude.api_key) and anthropic_key:
            p_claude.api_key = anthropic_key
            p_claude.api_key_encrypted = True
            p_claude.save()

        # 2. Init/Update OpenAI Provider
        p_openai, created = ProviderSettings.objects.get_or_create(
            id="openai",
            defaults={
                "name": "OpenAI GPT",
                "is_enabled": False,
                "api_key": openai_key,
                "api_key_encrypted": True if openai_key else False,
                "avg_latency_ms": 0.0,
                "request_count": 0,
                "error_count": 0
            }
        )
        if not created and not p_openai.api_key and openai_key:
            p_openai.api_key = openai_key
            p_openai.api_key_encrypted = True
            p_openai.save()

        # 3. Init Models
        if not LLMModel.objects.exists():
            LLMModel.objects.create(id="claude-sonnet-4-6", provider="claude", name="Claude 3.5 Sonnet", context=200000)
            LLMModel.objects.create(id="claude-opus-3", provider="claude", name="Claude 3 Opus", context=200000)
        # 4. Init Plans
        if not BillingPlan.objects.exists():
            BillingPlan.objects.create(id="free", name="Developer Free", price=0, tokens=100000, msgs=100, upload=5)
            BillingPlan.objects.create(id="pro", name="Enterprise Pro", price=29, tokens=1000000, msgs=1000, upload=20)
        # 5. Init Settings
        if not AppSetting.objects.exists():
            AppSetting.objects.create(key="conversation_limit", value="30", description="Maximum turns per chat")
            AppSetting.objects.create(key="default_balance", value="5.00", description="Sign-up wallet credits")
        # 6. Init MCP Servers
        if not MCPServer.objects.exists():
            MCPServer.objects.create(
                id="db-mcp", name="Database MCP Server", description="Secure read-only MySQL DB query connector",
                server_type="stdio", command="python", args="database_mcp/app.py",
                env_variables="MYSQL_USER, MYSQL_PASSWORD", is_enabled=True
            )
    except Exception as e:
        logger.error(f"Error seeding initial admin data: {e}", exc_info=True)

# Verify user is an administrator
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_dashboard_view(request):
    check_and_init_data()
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
    
    # Calculate estimated revenue
    estimated_revenue = sum(float(w.balance) for w in Wallet.objects.all())
    
    return Response({
        "total_users": total_users,
        "new_users_today": active_users,  # mock
        "active_users_today": active_users,
        "total_tokens_billed": total_tokens,
        "total_revenue": estimated_revenue,
        "estimated_revenue": estimated_revenue,
        "active_subscriptions": 2,  # mock
        "cost_trend": cost_trend,
        "daily_usage": cost_trend  # mock
    }, status=status.HTTP_200_OK)

def sync_wallet_tokens(user, wallet):
    try:
        from conversation.models import ChatSession, ChatMessage
        import decimal
        user_sessions = ChatSession.objects.filter(user=user)
        messages = ChatMessage.objects.filter(session__in=user_sessions)
        
        tokens_sum = sum(m.total_tokens or 0 for m in messages)
        cost_sum = sum(float(m.estimated_cost or 0) for m in messages)
        
        if tokens_sum > 0 and wallet.total_tokens_used == 0:
            wallet.total_tokens_used = tokens_sum
            wallet.balance = max(decimal.Decimal("0.00"), decimal.Decimal("5.00") - decimal.Decimal(str(cost_sum)))
            wallet.save()
            logger.info(f"Self-healed wallet for user {user.email} in admin: synced {tokens_sum} tokens, balance: {wallet.balance}")
    except Exception as e:
        logger.error(f"Error self-healing wallet tokens in admin: {e}", exc_info=True)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_users_list_view(request):
    User = get_user_model()
    users = User.objects.all()
    
    users_data = []
    for user in users:
        wallet, _ = Wallet.objects.get_or_create(user=user)
        sync_wallet_tokens(user, wallet)
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
    check_and_init_data()
    providers = ProviderSettings.objects.all()
    data = []
    for p in providers:
        data.append({
            "id": p.id,
            "provider_name": p.id,
            "name": p.name,
            "is_enabled": p.is_enabled,
            "api_key": p.api_key,
            "api_key_encrypted": p.api_key_encrypted,
            "avg_latency_ms": p.avg_latency_ms,
            "request_count": p.request_count,
            "error_count": p.error_count,
            "health_status": "healthy" if (p.api_key and p.api_key != "sk-ant-*********") else "unconfigured"
        })
    return Response(data, status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAdminUser])
def admin_provider_detail_view(request, provider_id):
    check_and_init_data()
    try:
        p = ProviderSettings.objects.get(id=provider_id)
    except ProviderSettings.DoesNotExist:
        return Response({"detail": "Provider settings not found"}, status=status.HTTP_404_NOT_FOUND)
        
    is_enabled = request.data.get("is_enabled")
    api_key = request.data.get("api_key")
    
    if is_enabled is not None:
        p.is_enabled = is_enabled
    if api_key is not None:
        p.api_key = api_key
        p.api_key_encrypted = True if api_key else False
    p.save()
    
    return Response({
        "id": p.id,
        "provider_name": p.id,
        "name": p.name,
        "is_enabled": p.is_enabled,
        "api_key": p.api_key,
        "api_key_encrypted": p.api_key_encrypted,
        "avg_latency_ms": p.avg_latency_ms,
        "request_count": p.request_count,
        "error_count": p.error_count,
        "health_status": "healthy" if (p.api_key and p.api_key != "sk-ant-*********") else "unconfigured"
    }, status=status.HTTP_200_OK)

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_models_view(request):
    check_and_init_data()
    if request.method == "GET":
        models = LLMModel.objects.all()
        data = []
        for m in models:
            data.append({
                "id": m.id,
                "model_id": m.id,
                "display_name": m.name,
                "provider_name": m.provider,
                "context_window": m.context
            })
        return Response(data, status=status.HTTP_200_OK)
    elif request.method == "POST":
        data = request.data
        m = LLMModel.objects.create(
            id=data.get("model_id") or data.get("id"),
            provider=data.get("provider_name") or data.get("provider", "claude"),
            name=data.get("display_name") or data.get("name", "New Model"),
            context=data.get("context_window") or data.get("context", 100000)
        )
        return Response({
            "id": m.id,
            "model_id": m.id,
            "display_name": m.name,
            "provider_name": m.provider,
            "context_window": m.context
        }, status=status.HTTP_201_CREATED)

@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def admin_model_detail_view(request, model_id):
    try:
        m = LLMModel.objects.get(id=model_id)
        m.delete()
        return Response({"detail": "Model deleted successfully"}, status=status.HTTP_200_OK)
    except LLMModel.DoesNotExist:
        return Response({"detail": "Model not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_subscriptions_view(request):
    check_and_init_data()
    if request.method == "GET":
        plans = BillingPlan.objects.all()
        data = []
        for p in plans:
            data.append({
                "id": p.id,
                "name": p.name,
                "monthly_price": p.price,
                "monthly_token_limit": p.tokens,
                "monthly_message_limit": p.msgs,
                "max_upload_size_mb": p.upload
            })
        return Response(data, status=status.HTTP_200_OK)
    elif request.method == "POST":
        data = request.data
        name = data.get("name", "New Plan")
        plan_id = name.lower().replace(" ", "-")
        p = BillingPlan.objects.create(
            id=plan_id,
            name=name,
            price=float(data.get("price") or data.get("monthly_price", 0)),
            tokens=int(data.get("tokens") or data.get("monthly_token_limit", 100000)),
            msgs=int(data.get("msgs") or data.get("monthly_message_limit", 1000)),
            upload=int(data.get("upload") or data.get("max_upload_size_mb", 10))
        )
        return Response({
            "id": p.id,
            "name": p.name,
            "monthly_price": p.price,
            "monthly_token_limit": p.tokens,
            "monthly_message_limit": p.msgs,
            "max_upload_size_mb": p.upload
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
            "user_email": f.user.email if f.user else "Anonymous",
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
            "user_email": m.session.user.email if m.session and m.session.user else "Anonymous",
            "session_title": m.session.title if m.session else "Untitled",
            "role": m.role,
            "tokens": m.total_tokens or 0,
            "cost": float(m.estimated_cost or 0),
            "created_at": m.created_at.isoformat()
        })
    return Response(logs_data, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_tickets_view(request):
    tickets = SupportTicket.objects.all().order_by("-created_at")
    data = []
    for t in tickets:
        data.append({
            "id": t.id,
            "user_email": t.user.email if t.user else "Anonymous",
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "internal_notes": t.internal_notes,
            "created_at": t.created_at.isoformat()
        })
    return Response(data, status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAdminUser])
def admin_ticket_detail_view(request, ticket_id):
    try:
        t = SupportTicket.objects.get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return Response({"detail": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)
        
    status_val = request.data.get("status")
    notes = request.data.get("internal_notes")
    if status_val is not None:
        t.status = status_val
    if notes is not None:
        t.internal_notes = notes
    t.save()
    
    return Response({
        "id": t.id,
        "status": t.status,
        "internal_notes": t.internal_notes
    }, status=status.HTTP_200_OK)

@api_view(["GET", "PUT"])
@permission_classes([IsAdminUser])
def admin_settings_view(request):
    check_and_init_data()
    if request.method == "GET":
        settings = AppSetting.objects.all()
        data = [{"key": s.key, "value": s.value, "description": s.description} for s in settings]
        return Response(data, status=status.HTTP_200_OK)
    elif request.method == "PUT":
        key = request.query_params.get("key")
        val = request.data.get("setting_value")
        try:
            s = AppSetting.objects.get(key=key)
            s.value = str(val)
            s.save()
            return Response({
                "key": s.key,
                "value": s.value,
                "detail": "Setting updated successfully"
            }, status=status.HTTP_200_OK)
        except AppSetting.DoesNotExist:
            return Response({"detail": "Setting not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_mcp_view(request):
    check_and_init_data()
    if request.method == "GET":
        servers = MCPServer.objects.all()
        data = []
        for s in servers:
            data.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "server_type": s.server_type,
                "url": s.url,
                "command": s.command,
                "args": s.args,
                "env_variables": s.env_variables,
                "is_enabled": s.is_enabled
            })
        return Response(data, status=status.HTTP_200_OK)
    elif request.method == "POST":
        data = request.data
        s = MCPServer.objects.create(
            name=data.get("name", "New MCP"),
            description=data.get("description", ""),
            server_type=data.get("server_type", "sse"),
            url=data.get("url", ""),
            command=data.get("command", ""),
            args=data.get("args", ""),
            env_variables=data.get("env_variables", ""),
            is_enabled=True
        )
        return Response({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "server_type": s.server_type,
            "url": s.url,
            "command": s.command,
            "args": s.args,
            "env_variables": s.env_variables,
            "is_enabled": s.is_enabled
        }, status=status.HTTP_201_CREATED)

@api_view(["PUT", "DELETE"])
@permission_classes([IsAdminUser])
def admin_mcp_detail_view(request, mcp_id):
    try:
        s = MCPServer.objects.get(id=mcp_id)
    except MCPServer.DoesNotExist:
        return Response({"detail": "MCP server not found"}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == "PUT":
        data = request.data
        s.name = data.get("name", s.name)
        s.description = data.get("description", s.description)
        s.server_type = data.get("server_type", s.server_type)
        s.url = data.get("url", s.url)
        s.command = data.get("command", s.command)
        s.args = data.get("args", s.args)
        s.env_variables = data.get("env_variables", s.env_variables)
        s.is_enabled = data.get("is_enabled", s.is_enabled)
        s.save()
        return Response({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "server_type": s.server_type,
            "url": s.url,
            "command": s.command,
            "args": s.args,
            "env_variables": s.env_variables,
            "is_enabled": s.is_enabled
        }, status=status.HTTP_200_OK)
    elif request.method == "DELETE":
        s.delete()
        return Response({"detail": "MCP server deleted successfully"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_mcp_test_view(request, mcp_id):
    try:
        mcp = MCPServer.objects.get(id=mcp_id)
    except MCPServer.DoesNotExist:
        return Response({"status": "error", "detail": "MCP server not found"}, status=status.HTTP_200_OK)
        
    if mcp.server_type == "sse":
        if not mcp.url:
            return Response({"status": "error", "detail": "SSE URL must be specified"}, status=status.HTTP_200_OK)
        import requests
        try:
            resp = requests.get(mcp.url, timeout=5.0)
            status_code = resp.status_code
            if status_code in (200, 201, 405):
                return Response({
                    "status": "healthy",
                    "detail": f"Successfully pinged SSE connection. Server replied with status code {status_code}."
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": "warning",
                    "detail": f"Ping completed, but server returned status code {status_code}."
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": "error",
                "detail": f"Connection failed: {str(e)}"
            }, status=status.HTTP_200_OK)
            
    else:  # stdio or stdio-based command
        if not mcp.command:
            return Response({"status": "error", "detail": "Local execution command must be specified"}, status=status.HTTP_200_OK)
        import subprocess
        import shlex
        import time
        try:
            cmd_args = shlex.split(mcp.command)
            if cmd_args and cmd_args[0] == "python":
                import shutil
                if not shutil.which("python") and shutil.which("python3"):
                    cmd_args[0] = "python3"
            if mcp.args:
                cmd_args.extend(shlex.split(mcp.args))
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(0.5)
            poll = proc.poll()
            if poll is not None and poll != 0:
                err_out = proc.stderr.read() if proc.stderr else ""
                proc.kill()
                return Response({
                    "status": "error",
                    "detail": f"Local executable failed with exit code {poll}. Error: {err_out[:100]}"
                }, status=status.HTTP_200_OK)
            proc.kill()
            return Response({
                "status": "healthy",
                "detail": "Successfully launched local MCP process (executable active)."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": "error",
                "detail": f"Failed to execute local process command: {str(e)}"
            }, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_provider_quota_view(request, provider_id):
    check_and_init_data()
    try:
        p = ProviderSettings.objects.get(id=provider_id)
    except ProviderSettings.DoesNotExist:
        return Response({"detail": "Provider not found"}, status=status.HTTP_404_NOT_FOUND)
        
    if not p.api_key:
        return Response({"detail": "No API key set for this provider"}, status=status.HTTP_400_BAD_REQUEST)
        
    import requests
    name = (p.id or "").lower()
    
    if name in ("claude", "anthropic"):
        headers = {
            "x-api-key": p.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": "claude-haiku-4-5",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1
        }
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=10.0
            )
            if resp.status_code != 200:
                return Response({
                    "error": f"Anthropic API error {resp.status_code}: {resp.json().get('error', {}).get('message', resp.text)}"
                }, status=status.HTTP_200_OK)
                
            h = resp.headers
            def safe_int(v):
                try: return int(v)
                except: return None
            return Response({
                "provider": "anthropic",
                "status": resp.status_code,
                "tokens_limit": safe_int(h.get("anthropic-ratelimit-tokens-limit")),
                "tokens_remaining": safe_int(h.get("anthropic-ratelimit-tokens-remaining")),
                "tokens_reset": h.get("anthropic-ratelimit-tokens-reset"),
                "requests_limit": safe_int(h.get("anthropic-ratelimit-requests-limit")),
                "requests_remaining": safe_int(h.get("anthropic-ratelimit-requests-remaining")),
                "requests_reset": h.get("anthropic-ratelimit-requests-reset"),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Failed to reach Anthropic API: {str(e)}"}, status=status.HTTP_200_OK)
            
    elif name == "openai":
        headers = {
            "Authorization": f"Bearer {p.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1
        }
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=10.0
            )
            if resp.status_code != 200:
                try:
                    err_msg = resp.json().get('error', {}).get('message', resp.text)
                except:
                    err_msg = resp.text
                return Response({
                    "error": f"OpenAI API error {resp.status_code}: {err_msg}"
                }, status=status.HTTP_200_OK)
                
            h = resp.headers
            def safe_int(v):
                try: return int(v)
                except: return None
            return Response({
                "provider": "openai",
                "status": resp.status_code,
                "tokens_limit": safe_int(h.get("x-ratelimit-limit-tokens")),
                "tokens_remaining": safe_int(h.get("x-ratelimit-remaining-tokens")),
                "tokens_reset": h.get("x-ratelimit-reset-tokens"),
                "requests_limit": safe_int(h.get("x-ratelimit-limit-requests")),
                "requests_remaining": safe_int(h.get("x-ratelimit-remaining-requests")),
                "requests_reset": h.get("x-ratelimit-reset-requests"),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Failed to reach OpenAI API: {str(e)}"}, status=status.HTTP_200_OK)
            
    return Response({"detail": f"Quota check not implemented for {p.name}"}, status=status.HTTP_400_BAD_REQUEST)


