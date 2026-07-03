import json
import logging
import asyncio
import uuid
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from conversation.controller import get_conversation_manager
from conversation.schemas.responses import ChatResponse

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # 1. Parse token from query string
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = {}
        for param in query_string.split("&"):
            if "=" in param:
                k, v = param.split("=", 1)
                params[k] = v
        token = params.get("token")
        
        if not token:
            logger.warning("WebSocket connection attempt without token.")
            await self.close(code=4003)
            return

        # 2. Validate token and authenticate user
        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            User = get_user_model()
            self.user = await User.objects.aget(id=user_id)
            self.scope["user"] = self.user
        except Exception as e:
            logger.warning(f"WebSocket token validation failed: {e}")
            await self.close(code=4003)
            return

        await self.accept()
        logger.info(f"WebSocket connected for user {self.user.email}")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected with code {close_code}")

    async def receive_json(self, content):
        action = content.get("action")
        if action == "message":
            conversation_id = content.get("conversation_id")
            prompt = content.get("prompt")
            provider = content.get("provider", "claude")
            model = content.get("model", "claude-sonnet-4-6")
            attachment_ids = content.get("attachment_ids", [])
            memory_updates = content.get("memory_updates", None)

            # Spawn as task to avoid blocking the websocket receive loop
            asyncio.create_task(
                self.handle_message_turn(conversation_id, prompt, provider, model, attachment_ids, memory_updates)
            )
        elif action == "stop":
            # stop generation if requested
            pass

    async def handle_message_turn(self, conversation_id, prompt, provider, model, attachment_ids, memory_updates):
        print(f"[WS TURN START] conv: {conversation_id}, prompt: {prompt}, attachment_ids: {attachment_ids}", flush=True)
        try:
            # Generate a new unique message ID for the assistant's reply
            assistant_message_id = str(uuid.uuid4())
            
            # 1. Get the conversation manager
            manager = get_conversation_manager()
            
            # Verify session ownership
            from conversation.models.session import ChatSession
            try:
                await ChatSession.objects.aget(session_id=conversation_id, user=self.user)
            except ChatSession.DoesNotExist:
                logger.warning(f"User {self.user.email} attempted to access unauthorized session {conversation_id}")
                await self.send_json({
                    "conversation_id": conversation_id,
                    "error": "Access Denied: Session does not belong to you."
                })
                return
            
            # 2. Run the full message processing loop
            # This executes privacy engine, Claude calls, MCP tool calls, database validation, etc.
            chat_response: ChatResponse = await manager.process_message(
                session_id=conversation_id,
                content=prompt,
                role="user",
                memory_updates=memory_updates,
                attachment_ids=attachment_ids
            )
            
            content = chat_response.response_content
            telemetry = chat_response.token_usage
            
            # Fetch updated session to capture LLM-generated title
            try:
                session_obj = await ChatSession.objects.aget(session_id=conversation_id)
                session_title = session_obj.title
            except Exception:
                session_title = None

            # 3. Stream the response content token-by-token (simulated stream for visual smooth rendering)
            # We stream chunks of 3-7 characters with a tiny sleep to simulate streaming.
            chunk_size = 5
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                await self.send_json({
                    "event": "token",
                    "conversation_id": conversation_id,
                    "message_id": assistant_message_id,
                    "token": chunk
                })
                await asyncio.sleep(0.015) # 15ms typing delay
            
            # 4. Finalize the message stream
            await self.send_json({
                "event": "done",
                "conversation_id": conversation_id,
                "message_id": assistant_message_id,
                "content": content,
                "title": session_title,
                "telemetry": {
                    "prompt_tokens": telemetry.prompt_tokens,
                    "completion_tokens": telemetry.completion_tokens,
                    "cache_read_tokens": 0, # Placeholder
                    "cost": float(telemetry.estimated_cost)
                }
            })
            
        except Exception as e:
            logger.error(f"Error during message streaming: {e}", exc_info=True)
            await self.send_json({
                "conversation_id": conversation_id,
                "error": str(e)
            })
