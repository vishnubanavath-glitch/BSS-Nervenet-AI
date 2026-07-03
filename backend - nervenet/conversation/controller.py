import json
import logging
import os
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError as PydanticValidationError

from conversation.exceptions import (
    SessionNotFoundException,
    ValidationError,
    LLMRequestException,
    ConversationEngineException
)
from conversation.schemas.requests import CreateSessionRequest, SendMessageRequest
from conversation.utils.helpers import generate_uuid
from conversation.utils.validators import validate_uuid
from conversation.storage import (
    DjangoSessionStore,
    DjangoHistoryStore,
    DjangoMemoryStore,
    DjangoSummaryStore
)
from conversation.session_manager import SessionManager
from conversation.history_manager import HistoryManager
from conversation.memory_manager import MemoryManager
from conversation.summary_manager import SummaryManager
from conversation.prompt_builder import PromptBuilder
from conversation.llm_manager import LLMManager, AnthropicLLMProvider
from conversation.token_manager import TokenManager
from conversation.title_generator import TitleGenerator
from conversation.manager import ConversationManager
from conversation.privacy_engine import PrivacyEngine

logger = logging.getLogger(__name__)

def get_conversation_manager() -> ConversationManager:
    """Dependency injection helper to wire up storage repositories and managers."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValidationError("ANTHROPIC_API_KEY environment variable is required.")
    provider = AnthropicLLMProvider(api_key=api_key)
        
    session_repo = DjangoSessionStore()
    history_repo = DjangoHistoryStore()
    memory_repo = DjangoMemoryStore()
    summary_repo = DjangoSummaryStore()
    
    return ConversationManager(
        session_manager=SessionManager(session_repo),
        history_manager=HistoryManager(history_repo),
        memory_manager=MemoryManager(memory_repo),
        summary_manager=SummaryManager(summary_repo, history_repo),
        prompt_builder=PromptBuilder(),
        llm_manager=LLMManager(provider),
        token_manager=TokenManager(),
        title_generator=TitleGenerator()
    )

@csrf_exempt
async def create_session_view(request):
    """POST /api/sessions/ - Initialize a new conversation session.
    GET /api/sessions/ - List all active sessions.
    """
    manager = get_conversation_manager()
    
    if request.method == "GET":
        try:
            sessions = await manager._session_manager._session_repo.list_active()
            sessions_data = []
            for s in sessions:
                sessions_data.append({
                    "session_id": str(s.session_id),
                    "title": s.title or "Untitled Session",
                    "created_at": s.created_at.isoformat(),
                    "status": s.status
                })
            return JsonResponse({"sessions": sessions_data}, status=200)
        except Exception as e:
            logger.error(f"Failed to list active sessions: {e}", exc_info=True)
            return JsonResponse({"error": "Internal server error"}, status=500)
            
    elif request.method == "POST":
        try:
            body = {}
            if request.body:
                body = json.loads(request.body)
                
            # Validate input schema
            req_data = CreateSessionRequest(**body)
            
            # Initialize
            session_id = generate_uuid()
            session = await manager.initialize_session(session_id, req_data.title)
            
            return JsonResponse({
                "session_id": str(session.session_id),
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "status": session.status
            }, status=201)
        except PydanticValidationError as e:
            return JsonResponse({"error": "Validation error", "details": e.errors()}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            logger.error(f"Failed to create session: {e}", exc_info=True)
            return JsonResponse({"error": "Internal server error"}, status=500)
    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
async def session_detail_view(request, session_id):
    """GET/DELETE /api/sessions/<session_id>/ - Load or delete a session."""
    manager = get_conversation_manager()
    
    try:
        validate_uuid(session_id)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if request.method == "GET":
        try:
            session = await manager._session_manager.load_session(session_id)
            messages = await manager._history_manager.get_complete_history(session_id)
            memory = await manager._memory_manager.get_memory(session_id)
            summary = await manager._summary_manager.get_summary(session_id)
            
            # Initialize PrivacyEngine and load saved state from memory
            privacy_engine = PrivacyEngine()
            privacy_engine.load_state(memory.get("_privacy_state", {}))
            
            history_data = []
            for msg in messages:
                content_to_show = msg.content
                if msg.role == "assistant":
                    content_to_show = privacy_engine.detokenize_text(msg.content)
                history_data.append({
                    "message_id": str(msg.message_id),
                    "role": msg.role,
                    "content": content_to_show,
                    "created_at": msg.created_at.isoformat()
                })
                
            summary_to_show = summary
            if summary:
                summary_to_show = privacy_engine.detokenize_text(summary)
                
            filtered_memory = {k: v for k, v in memory.items() if k != "_privacy_state"}
            
            return JsonResponse({
                "session_id": str(session.session_id),
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "status": session.status,
                "summary": summary_to_show,
                "memory": filtered_memory,
                "history": history_data
            }, status=200)
        except SessionNotFoundException as e:
            return JsonResponse({"error": str(e)}, status=404)
        except Exception as e:
            logger.error(f"Failed to retrieve session details: {e}", exc_info=True)
            return JsonResponse({"error": "Internal server error"}, status=500)
            
    elif request.method == "DELETE":
        try:
            deleted = await manager._session_manager.delete_session(session_id)
            if not deleted:
                return JsonResponse({"error": "Session not found"}, status=404)
            return JsonResponse({"message": f"Session {session_id} and all related data deleted successfully"}, status=200)
        except Exception as e:
            logger.error(f"Failed to delete session: {e}", exc_info=True)
            return JsonResponse({"error": "Internal server error"}, status=500)
            
    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
async def send_message_view(request, session_id):
    """POST /api/sessions/<session_id>/messages/ - Send a user message to the session."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    try:
        validate_uuid(session_id)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)
        
    try:
        body = {}
        if request.body:
            body = json.loads(request.body)
            
        req_data = SendMessageRequest(**body)
        
        manager = get_conversation_manager()
        
        chat_response = await manager.process_message(
            session_id=session_id,
            content=req_data.content,
            role=req_data.role,
            memory_updates=req_data.memory_updates
        )
        
        # Serialize model output response
        return JsonResponse(chat_response.model_dump(), status=200)
        
    except SessionNotFoundException as e:
        return JsonResponse({"error": str(e)}, status=404)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except PydanticValidationError as e:
        return JsonResponse({"error": "Validation error", "details": e.errors()}, status=400)
    except LLMRequestException as e:
        logger.error(f"LLM Communication failed: {e}")
        return JsonResponse({"error": str(e)}, status=502)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"Failed to process message view: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)
