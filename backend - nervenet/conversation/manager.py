import logging
import sys
import os
import json
from typing import Optional, Dict, Any, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from conversation.models.session import ChatSession
from conversation.session_manager import SessionManager
from conversation.history_manager import HistoryManager
from conversation.memory_manager import MemoryManager
from conversation.summary_manager import SummaryManager
from conversation.prompt_builder import PromptBuilder
from conversation.llm_manager import LLMManager, LLMResponse
from conversation.token_manager import TokenManager
from conversation.title_generator import TitleGenerator
from conversation.privacy_engine import PrivacyEngine
from conversation.constants import (
    PRESERVE_RECENT_MESSAGES_COUNT,
    CLAUDE_INPUT_COST_PER_TOKEN,
    CLAUDE_OUTPUT_COST_PER_TOKEN
)
from conversation.schemas.responses import ChatResponse, MessageResponse, TokenUsageSchema

logger = logging.getLogger(__name__)

def decrypt_tool_args(tool_input: Any, privacy_engine: PrivacyEngine) -> Any:
    if not privacy_engine or not tool_input:
        return tool_input
    def _decrypt(val):
        if isinstance(val, str):
            return privacy_engine.detokenize_text(val)
        elif isinstance(val, dict):
            return {k: _decrypt(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [_decrypt(item) for item in val]
        return val
    return _decrypt(tool_input)

def encrypt_tool_result(result_text: str, privacy_engine: PrivacyEngine) -> str:
    if not privacy_engine:
        return result_text
    try:
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            import ast
            data = ast.literal_eval(result_text)
            
        if isinstance(data, dict) and "columns" in data and "rows" in data:
            columns = data["columns"]
            rows = data["rows"]
            encrypted_rows = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                encrypted_dict = privacy_engine.encrypt_record(row_dict)
                encrypted_rows.append([encrypted_dict.get(col, val) for col, val in zip(columns, row)])
            data["rows"] = encrypted_rows
            return json.dumps(data)
            
        if isinstance(data, list):
            encrypted_data = [privacy_engine.encrypt_record(r) for r in data]
        elif isinstance(data, dict):
            encrypted_data = privacy_engine.encrypt_record(data)
        else:
            encrypted_data = data
        return json.dumps(encrypted_data)
    except Exception:
        return privacy_engine.tokenize_text(result_text)

class ConversationManager:
    def __init__(
        self,
        session_manager: SessionManager,
        history_manager: HistoryManager,
        memory_manager: MemoryManager,
        summary_manager: SummaryManager,
        prompt_builder: PromptBuilder,
        llm_manager: LLMManager,
        token_manager: TokenManager,
        title_generator: TitleGenerator
    ):
        self._session_manager = session_manager
        self._history_manager = history_manager
        self._memory_manager = memory_manager
        self._summary_manager = summary_manager
        self._prompt_builder = prompt_builder
        self._llm_manager = llm_manager
        self._token_manager = token_manager
        self._title_generator = title_generator

    async def initialize_session(self, session_id: str, title: Optional[str] = None) -> ChatSession:
        """Create and initialize a new empty session, memory context, and summary record."""
        session = await self._session_manager.create_session(session_id, title)
        # Initialize empty memory and summary models
        await self._memory_manager.update_memory(session_id, {})
        await self._summary_manager.update_summary(session_id, "", None)
        return session

    async def process_message(
        self,
        session_id: str,
        content: str,
        role: str = "user",
        memory_updates: Optional[Dict[str, Any]] = None,
        attachment_ids: Optional[List[str]] = None
    ) -> ChatResponse:
        """Orchestrate the complete pipeline for a new incoming message."""
        # 1. Load and validate session existence
        session = await self._session_manager.load_session(session_id)
        
        # 2. Update/retrieve runtime memory context
        if memory_updates:
            memory = await self._memory_manager.update_memory(session_id, memory_updates)
        else:
            memory = await self._memory_manager.get_memory(session_id)
            
        # Initialize PrivacyEngine and load saved state from memory
        privacy_engine = PrivacyEngine()
        privacy_engine.load_state(memory.get("_privacy_state", {}))

        # 3. Store incoming user message in history
        user_msg = await self._history_manager.add_message(
            session_id=session_id,
            role=role,
            content=content
        )

        # 3b. Resolve attachments and link them to the user message
        image_blocks: List[Dict] = []
        text_attachments: List[str] = []
        print(f"[ATTACHMENT RESOLVE] Processing attachments: {attachment_ids}", flush=True)
        if attachment_ids:
            import base64
            from asgiref.sync import sync_to_async
            from conversation.models.attachment import Attachment

            for att_id in attachment_ids:
                try:
                    att = await sync_to_async(Attachment.objects.get)(id=att_id)
                    print(f"[ATTACHMENT RESOLVE] Found attachment in DB: {att.filename}, type={att.mime_type}, has_text={bool(att.extracted_text)}, size={att.file_size}", flush=True)
                    # Link attachment to this message
                    att.message = user_msg
                    await sync_to_async(att.save)()
                    
                    mime = att.mime_type or ""
                    if mime.startswith("image/"):
                        # Load image file and base64-encode it for the Claude vision API
                        file_path = att.file.path
                        with open(file_path, "rb") as fh:
                            img_data = fh.read()
                        b64 = base64.b64encode(img_data).decode("utf-8")
                        image_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64
                            }
                        })
                        print(f"[ATTACHMENT RESOLVE] Image block created successfully for {att.filename}", flush=True)
                    elif mime == "application/pdf":
                        text_len = len(att.extracted_text) if att.extracted_text else 0
                        if text_len >= 50:
                            # Standard PDF with extractable text
                            text_attachments.append(
                                f"=== Attachment: {att.filename} ===\n{att.extracted_text}\n=== End of Attachment ===\n"
                            )
                            print(f"[ATTACHMENT RESOLVE] PDF Text attachment injected: {att.filename} ({text_len} chars)", flush=True)
                        else:
                            # Scanned PDF! Extract page images
                            print(f"[ATTACHMENT RESOLVE] PDF {att.filename} has minimal text ({text_len} chars) - extracting page images", flush=True)
                            try:
                                from pypdf import PdfReader
                                reader = PdfReader(att.file.path)
                                img_count = 0
                                for page in reader.pages:
                                    for img in page.images:
                                        if img_count >= 5:  # Cap at 5 images
                                            break
                                        name = img.name.lower()
                                        media_type = "image/jpeg"
                                        if name.endswith(".png"):
                                            media_type = "image/png"
                                        elif name.endswith(".gif"):
                                            media_type = "image/gif"
                                        elif name.endswith(".webp"):
                                            media_type = "image/webp"
                                        
                                        base64_data = base64.b64encode(img.data).decode("utf-8")
                                        image_blocks.append({
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": media_type,
                                                "data": base64_data
                                            }
                                        })
                                        img_count += 1
                                print(f"[ATTACHMENT RESOLVE] Extracted {img_count} page images from PDF {att.filename}", flush=True)
                            except Exception as pdf_err:
                                print(f"[ATTACHMENT RESOLVE] Failed to extract page images from PDF {att.filename}: {pdf_err}", flush=True)
                    elif att.extracted_text:
                        # For text-extractable files (DOCX, CSV, TXT…) inject as text
                        text_attachments.append(
                            f"=== Attachment: {att.filename} ===\n{att.extracted_text}\n=== End of Attachment ===\n"
                        )
                        print(f"[ATTACHMENT RESOLVE] Text attachment injected: {att.filename} ({len(att.extracted_text)} chars)", flush=True)
                    else:
                        print(f"[ATTACHMENT RESOLVE] Attachment {att.filename} has no extracted text and is not an image/PDF", flush=True)
                except Exception as e:
                    print(f"[ATTACHMENT RESOLVE] Failed to load attachment {att_id}: {e}", flush=True)
                    logger.warning(f"Failed to load attachment {att_id}: {e}")

        # Merge any text-attachment content into the prompt
        enriched_content = content
        if text_attachments:
            enriched_content = "\n\n".join(text_attachments) + "\n\n" + content
        print(f"[ATTACHMENT RESOLVE] Enriched content length: {len(enriched_content)}, image blocks: {len(image_blocks)}", flush=True)
        
        # 4. Fetch full history to determine what needs to be fed into the prompt builder
        full_history = await self._history_manager.get_complete_history(session_id)
        summary_obj = await self._summary_manager.get_summary_object(session_id)
        
        # 5. Extract only recent history that has not yet been condensed into the summary
        recent_history = []
        if summary_obj and summary_obj.last_processed_message_id:
            found_split = False
            for msg in full_history:
                if found_split:
                    recent_history.append(msg)
                elif msg.message_id == summary_obj.last_processed_message_id:
                    found_split = True
            # Fallback if the summarized message wasn't found (safety measure)
            if not found_split:
                recent_history = full_history
        else:
            recent_history = full_history
            
        # 6. Build the prompt payload
        # Note: recent_history currently contains the newly added user message at the end.
        # We pass history *before* the user message, and the current message content separately.
        history_before = [m for m in recent_history if m.message_id != user_msg.message_id]
        
        # Filter _privacy_state out of memory for prompt builder
        filtered_memory = {k: v for k, v in memory.items() if k != "_privacy_state"}

        prompt_payload = self._prompt_builder.build_prompt(
            system_prompt=None,
            summary=summary_obj.summary if summary_obj else None,
            recent_history=history_before,
            current_message=enriched_content,
            memory=filtered_memory,
            privacy_engine=privacy_engine,
            image_blocks=image_blocks if image_blocks else None
        )
        
        # Logging raw user prompt and encrypted prompt sent to LLM
        encrypted_prompt = prompt_payload["messages"][-1]["content"]
        # print(f"\n[PRIVACY DEBUG] 1. user prompt: {content}", flush=True)
        # print(f"[PRIVACY DEBUG] 2. encrypted prompt llm recieves: {encrypted_prompt}", flush=True)
        # logger.info(f"[PRIVACY DEBUG] 1. user prompt: {content}")
        # logger.info(f"[PRIVACY DEBUG] 2. encrypted prompt llm recieves: {encrypted_prompt}")
        
        # 7. Call LLM with MCP tool-calling loop
        python_cmd = sys.executable or "python"
        mcp_app_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "database_mcp",
            "app.py"
        )
        server_params = StdioServerParameters(
            command=python_cmd,
            args=[mcp_app_path],
            env=os.environ.copy()
        )

        prompt_tokens = 0
        completion_tokens = 0
        final_text = ""

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as mcp_session:
                    await mcp_session.initialize()
                    mcp_tools = await mcp_session.list_tools()
                    anthropic_tools = [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "input_schema": tool.inputSchema
                        }
                        for tool in mcp_tools.tools
                    ]

                    messages_payload = prompt_payload["messages"]
                    system_prompt = prompt_payload["system"]
                    
                    max_turns = 10
                    turn = 0
                    
                    while turn < max_turns:
                        turn += 1
                        logger.info(f"Calling Claude (Turn {turn})...")
                        llm_resp = await self._llm_manager._provider.generate(
                            system=system_prompt,
                            messages=messages_payload,
                            max_tokens=4096,
                            temperature=0.5,
                            tools=anthropic_tools
                        )
                        
                        prompt_tokens += llm_resp.prompt_tokens
                        completion_tokens += llm_resp.completion_tokens
                        
                        tool_calls = []
                        text_content = ""
                        response_blocks = []
                        
                        for block in llm_resp.content_blocks:
                            block_type = block.type if hasattr(block, "type") else block.get("type", "text")
                            if block_type == "text":
                                txt = block.text if hasattr(block, "text") else block.get("text", "")
                                text_content += txt
                                response_blocks.append({"type": "text", "text": txt})
                            elif block_type == "tool_use":
                                tool_calls.append(block)
                                response_blocks.append({
                                    "type": "tool_use",
                                    "id": block.id if hasattr(block, "id") else block.get("id"),
                                    "name": block.name if hasattr(block, "name") else block.get("name"),
                                    "input": block.input if hasattr(block, "input") else block.get("input")
                                })

                        messages_payload.append({
                            "role": "assistant",
                            "content": response_blocks
                        })
                        
                        if not tool_calls:
                            final_text = text_content
                            break

                        tool_results = []
                        for tool in tool_calls:
                            tool_id = tool.id if hasattr(tool, "id") else tool.get("id")
                            tool_name = tool.name if hasattr(tool, "name") else tool.get("name")
                            tool_input = tool.input if hasattr(tool, "input") else tool.get("input")

                            decrypted_args = decrypt_tool_args(tool_input, privacy_engine)
                            # print(f"[PRIVACY DEBUG] 3. decrypted prompt mcp recieved: {decrypted_args}", flush=True)
                            # logger.info(f"[PRIVACY DEBUG] 3. decrypted prompt mcp recieved: {decrypted_args}")
                            
                            try:
                                mcp_result = await mcp_session.call_tool(tool_name, arguments=decrypted_args)
                                
                                result_text = ""
                                for item in mcp_result.content:
                                    item_type = item.type if hasattr(item, "type") else item.get("type", "text")
                                    if item_type == "text":
                                        result_text += item.text if hasattr(item, "text") else item.get("text", "")
                                        
                                encrypted_result = encrypt_tool_result(result_text, privacy_engine)
                                 # print(f"[PRIVACY DEBUG] 4. encrypted response mcp returned to llm: {encrypted_result}", flush=True)
                                 # logger.info(f"[PRIVACY DEBUG] 4. encrypted response mcp returned to llm: {encrypted_result}")
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": encrypted_result
                                })
                            except Exception as e:
                                logger.error(f"MCP Tool '{tool_name}' failed: {e}", exc_info=True)
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": f"Error calling tool: {str(e)}",
                                    "is_error": True
                                })

                        messages_payload.append({
                            "role": "user",
                            "content": tool_results
                        })
                    else:
                        raise RuntimeError("Exceeded maximum tool-calling turns.")
        except Exception as e:
            logger.error(f"Error in MCP client session / loop: {e}", exc_info=True)
            # Fallback to direct text response if MCP fails
            llm_resp = await self._llm_manager.generate_response(prompt_payload)
            prompt_tokens += llm_resp.prompt_tokens
            completion_tokens += llm_resp.completion_tokens
            final_text = llm_resp.content

        llm_response = LLMResponse(final_text, prompt_tokens, completion_tokens)
        # print(f"[PRIVACY DEBUG] 5. encrypted response llm gives before decrypt: {llm_response.content}", flush=True)
        # logger.info(f"[PRIVACY DEBUG] 5. encrypted response llm gives before decrypt: {llm_response.content}")
        
        # Save updated privacy engine state back to session memory
        memory["_privacy_state"] = privacy_engine.dump_state()
        await self._memory_manager.update_memory(session_id, {"_privacy_state": memory["_privacy_state"]})

        # 8. Calculate total transaction cost
        cost = self._token_manager.calculate_cost(
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens
        )
        
        # Update User's message with actual input tokens and its cost
        user_msg.prompt_tokens = llm_response.prompt_tokens
        user_msg.completion_tokens = 0
        user_msg.total_tokens = llm_response.prompt_tokens
        user_msg.estimated_cost = llm_response.prompt_tokens * CLAUDE_INPUT_COST_PER_TOKEN
        await user_msg.asave()
        
        # 9. Store Assistant's response in history
        assistant_msg = await self._history_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=llm_response.content,
            prompt_tokens=0,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.completion_tokens,
            estimated_cost=llm_response.completion_tokens * CLAUDE_OUTPUT_COST_PER_TOKEN
        )
        
        # Refresh full history list for title & token checks
        full_history.append(assistant_msg)
        
        # 10. Auto-generate title if this is the first turn and title is empty
        if not session.title:
            try:
                new_title = await self._title_generator.generate_title(
                    session=session,
                    first_messages=full_history,
                    llm_manager=self._llm_manager
                )
                session.title = new_title
                await self._session_manager.update_session(session)
            except Exception as e:
                logger.error(f"Error auto-generating session title: {e}", exc_info=True)
                
        # 11. Calculate token counts for summarization thresholds
        total_unsummarized_tokens = 0
        unsummarized_messages = []
        
        # Find messages after last processed summary
        if summary_obj and summary_obj.last_processed_message_id:
            found_split = False
            for msg in full_history:
                if found_split:
                    unsummarized_messages.append(msg)
                elif msg.message_id == summary_obj.last_processed_message_id:
                    found_split = True
        else:
            unsummarized_messages = full_history
            
        for msg in unsummarized_messages:
            if msg.total_tokens:
                total_unsummarized_tokens += msg.total_tokens
            else:
                total_unsummarized_tokens += self._token_manager.estimate_tokens(msg.content)
                
        # Trigger incremental summarization if threshold is crossed
        updated_summary_text = summary_obj.summary if summary_obj else None
        if self._token_manager.should_summarize(total_unsummarized_tokens):
            try:
                updated_summary_text = await self._summary_manager.summarize_history(
                    session_id=session_id,
                    llm_manager=self._llm_manager,
                    privacy_engine=privacy_engine
                )
            except Exception as e:
                logger.error(f"Failed to summarize conversation history: {e}", exc_info=True)
                
        # 12. Update last activity timestamp on the session
        await self._session_manager.update_last_activity(session_id)
        
        # 13. Map responses to schema structure
        recent_msg_responses = []
        # Re-fetch recent messages after potential summarization
        latest_summary_obj = await self._summary_manager.get_summary_object(session_id)
        
        active_history = []
        if latest_summary_obj and latest_summary_obj.last_processed_message_id:
            found_split = False
            for m in full_history:
                if found_split:
                    active_history.append(m)
                elif m.message_id == latest_summary_obj.last_processed_message_id:
                    found_split = True
            if not found_split:
                active_history = full_history
        else:
            active_history = full_history

        for m in active_history:
            usage_schema = None
            if m.total_tokens is not None:
                usage_schema = TokenUsageSchema(
                    prompt_tokens=m.prompt_tokens or 0,
                    completion_tokens=m.completion_tokens or 0,
                    total_tokens=m.total_tokens or 0,
                    estimated_cost=float(m.estimated_cost or 0)
                )
                
            # Detokenize assistant messages for display to the user
            content_to_show = m.content
            if m.role == "assistant":
                content_to_show = privacy_engine.detokenize_text(m.content)

            recent_msg_responses.append(
                MessageResponse(
                    message_id=str(m.message_id),
                    role=m.role,
                    content=content_to_show,
                    created_at=m.created_at,
                    token_usage=usage_schema
                )
            )
            
        # 14. Update Wallet tokens and deduct balance
        try:
            from conversation.models.wallet import Wallet
            from asgiref.sync import sync_to_async
            import decimal
            session_user = await sync_to_async(lambda: session.user)()
            wallet, _ = await Wallet.objects.aget_or_create(user=session_user)
            
            # Sum up current prompt and completion tokens
            wallet.total_tokens_used += llm_response.total_tokens
            
            # Deduct cost
            cost_dec = decimal.Decimal(str(cost))
            wallet.balance = max(decimal.Decimal("0.00"), wallet.balance - cost_dec)
            await wallet.asave()
            logger.info(f"Updated Wallet for user {session_user.email}: added {llm_response.total_tokens} tokens, deducted {cost_dec} balance (new balance: {wallet.balance})")
        except Exception as wallet_err:
            logger.error(f"Failed to update Wallet in manager: {wallet_err}", exc_info=True)
            
        return ChatResponse(
            session_id=str(session.session_id),
            response_content=privacy_engine.detokenize_text(llm_response.content),
            role="assistant",
            recent_history=recent_msg_responses,
            memory=filtered_memory,
            summary=updated_summary_text,
            token_usage=TokenUsageSchema(
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
                estimated_cost=cost
            )
        )
