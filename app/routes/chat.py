from flask import Blueprint, request, jsonify, send_file, current_app, Response, stream_with_context
from flask_login import login_required, current_user
from app import db, limiter, rate_limit_chat, rate_limit_attachment_upload, rate_limit_document_upload, rate_limit_improve_prompt
from app.models.chat import Chat, Message
from app.models.attachment import Attachment
from app.models.document import Document
from app.services.ai_service import AIService
from app.services.file_service import FileService
from app.services.rag_service import RAGService
import uuid
import os
import json
import io
import zipfile
import re
from datetime import datetime
import time
import requests as http_requests

bp = Blueprint('chat', __name__)

# Model list cache for available-models endpoint
# Structure: {provider: {'models': [...], 'timestamp': float}}
_model_list_cache = {}
MODEL_CACHE_TTL = 300  # 5 minutes in seconds


def _parse_distilled_summaries(summary_text: str) -> tuple:
    """
    Parse USER: and ASSISTANT: summaries from LLM response.

    Args:
        summary_text: The raw summary response from the LLM

    Returns:
        tuple: (user_summary, assistant_summary)
    """
    user_summary = ""
    assistant_summary = ""

    lines = summary_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.upper().startswith('USER:'):
            user_summary = line[5:].strip()
        elif line.upper().startswith('ASSISTANT:'):
            assistant_summary = line[10:].strip()

    # Fallback if parsing fails - use the whole response split in half
    if not user_summary and not assistant_summary:
        parts = summary_text.split('\n\n', 1)
        user_summary = parts[0][:300] if parts else summary_text[:150]
        assistant_summary = parts[1][:300] if len(parts) > 1 else summary_text[:150]

    return user_summary, assistant_summary


def _generate_distilled_context(user_msg, bot_msg, user_message_content: str, bot_response: str,
                                 model_provider: str, model_name, user_id: int, upload_folder: str):
    """
    Generate and store distilled summaries for user and bot messages.

    Args:
        user_msg: The user Message object to update
        bot_msg: The bot Message object to update
        user_message_content: The original user message content
        bot_response: The full bot response
        model_provider: The AI provider to use for summarization
        model_name: The model name (if specified)
        user_id: The current user's ID
        upload_folder: Path to upload folder
    """
    from flask import current_app

    try:
        # Strip thinking tags from bot response before summarization
        cleaned_response = re.sub(r'<think>.*?</think>', '', bot_response, flags=re.DOTALL).strip()

        # Truncate very long responses to avoid token limits in summarization
        truncated_response = cleaned_response[:4000] if len(cleaned_response) > 4000 else cleaned_response
        truncated_user = user_message_content[:2000] if len(user_message_content) > 2000 else user_message_content

        summarization_prompt = f"""Summarize the following conversation exchange. Be extremely brief - aim for 1-2 sentences each.

IMPORTANT: Write summaries as direct statements, NOT descriptions of what was said.
- WRONG: "The user asked about the capital" or "The assistant explained that..."
- CORRECT: "What is the capital of France?" or "The capital of France is Paris."

The user's message: {truncated_user}

The response given: {truncated_response}

Provide two ultra-brief summaries in this exact format:
USER: [Restate the user's question/request directly]
ASSISTANT: [State the key information from the response directly, as facts]"""

        summary_result = AIService.get_response(
            messages=[{"role": "user", "content": summarization_prompt}],
            provider=model_provider,
            model_name=model_name,
            user_id=user_id,
            upload_folder=upload_folder
        )

        if summary_result.get('response'):
            # Strip any thinking tags from the summary response itself
            summary_text = re.sub(r'<think>.*?</think>', '', summary_result['response'], flags=re.DOTALL).strip()
            user_summary, assistant_summary = _parse_distilled_summaries(summary_text)

            # Update messages with distilled content
            if user_summary:
                user_msg.distilled_content = user_summary
            if assistant_summary:
                bot_msg.distilled_content = assistant_summary

            db.session.commit()
            current_app.logger.info(f"Distilled context generated for messages {user_msg.id}, {bot_msg.id}")
        else:
            current_app.logger.warning(f"Distilled context: No response from summarization")

    except Exception as e:
        current_app.logger.warning(f"Distilled context generation failed: {str(e)}")
        # Don't fail the main response - just log and continue


@bp.route('/chat', methods=['POST'])
@login_required
@limiter.limit(rate_limit_chat)
def chat():
    """
    Main chat endpoint with streaming support - requires authentication
    Supports file attachments (images and documents)
    Returns Server-Sent Events (SSE) for streaming responses
    """
    data = request.get_json()

    message_content = data.get("message", "").strip()
    model_provider = data.get("model", "gemini")
    local_model_provider = data.get("local_model_provider", "lmstudio")
    session_id = data.get("session_id")
    model_name = data.get("model_name")
    attachments_data = data.get("attachments", [])  # List of uploaded file info
    local_vision_enabled = data.get("local_vision_enabled", False)  # User's vision toggle for local models

    if not message_content and not attachments_data:
        return jsonify({"error": "No message or attachments provided"}), 400

    # Apply sensitive information filter if enabled
    from app.models.admin_settings import AdminSettings
    if AdminSettings.is_sensitive_info_filter_enabled() and message_content:
        from app.services.sensitive_info_filter import SensitiveInfoFilter
        message_content = SensitiveInfoFilter.filter_message(message_content)

    # Child Safety: Get age-based system prompt if applicable
    age_system_prompt = None
    if current_user.date_of_birth:
        age_group = current_user.get_age_group()
        age_system_prompt = AdminSettings.get_age_based_system_prompt(age_group)

    # Map old model names to new provider names
    if model_provider == "simply":
        model_provider = local_model_provider

    # Find or create chat session
    if session_id:
        chat = Chat.query.filter_by(session_id=session_id).first()
        if not chat:
            return jsonify({"error": "Session not found"}), 404
    else:
        # Create new chat session
        session_id = str(uuid.uuid4())
        chat_name = " ".join(message_content.split()[:5]) if message_content else "New Chat"

        # Create chat for authenticated user
        chat = Chat(
            session_id=session_id,
            name=chat_name,
            model_provider=model_provider,
            model_name=model_name,
            user_id=current_user.id
        )
        db.session.add(chat)
        db.session.commit()

    # Count tokens for user message
    from app.services.token_service import TokenService
    user_input_tokens = TokenService.count_tokens(message_content) if message_content else 0

    # Save user message immediately
    user_msg = Message(
        chat_id=chat.id,
        role="user",
        content=message_content or "See attached files",
        model_used=model_name or model_provider,
        input_tokens=user_input_tokens,
        tokens_used=user_input_tokens,
        tokens_estimated=True  # Counted locally, not from API
    )
    db.session.add(user_msg)
    db.session.flush()  # Get user_msg.id before creating attachments

    # Save attachments if present
    if attachments_data:
        for att_data in attachments_data:
            attachment = Attachment(
                message_id=user_msg.id,
                original_filename=att_data['original_filename'],
                stored_filename=att_data['stored_filename'],
                file_path=att_data['file_path'],
                mime_type=att_data['mime_type'],
                file_size=att_data['file_size'],
                file_type=att_data['file_type']
            )
            db.session.add(attachment)

    db.session.commit()

    # Get chat history
    # Check if distilled context is enabled - use summaries instead of full content
    use_distilled_context = AdminSettings.is_distilled_context_enabled()

    messages = []
    for msg in chat.messages.all():
        # Use distilled content if enabled AND available, otherwise use full content
        if use_distilled_context and msg.distilled_content:
            content = msg.distilled_content
        else:
            content = msg.content

        msg_dict = {
            "role": "assistant" if msg.role == "bot" or msg.role == "assistant" else "user",
            "content": content
        }
        # Include attachments for historical messages (not distilled)
        if msg.attachments:
            msg_dict["attachments"] = [att.to_dict() for att in msg.attachments]
        messages.append(msg_dict)

    # RAG: Retrieve relevant document context if enabled
    # Skip RAG for Anthropic and xAI models - they can read documents natively
    rag_context = None
    use_rag = data.get("use_rag", True) and model_provider not in ('anthropic', 'xai')

    if use_rag and RAGService.is_enabled():
        try:
            # Check if user has any ready documents
            user_doc_count = Document.query.filter_by(
                user_id=current_user.id,
                status='ready'
            ).count()

            if user_doc_count > 0:
                # Retrieve relevant context for the user's message
                # Use embedding provider matching the chat model (Gemini/OpenAI)
                retrieved_chunks = RAGService.retrieve_context(
                    user_id=current_user.id,
                    query=message_content,
                    model_provider=model_provider
                )

                if retrieved_chunks:
                    rag_context = RAGService.format_context_for_prompt(retrieved_chunks)
                    current_app.logger.info(
                        f"RAG: Retrieved {len(retrieved_chunks)} chunks for user {current_user.id}"
                    )
        except Exception as e:
            current_app.logger.warning(f"RAG retrieval failed: {str(e)}")
            # Continue without RAG context if retrieval fails

    # Stream generator function
    def generate():
        user_id = current_user.id
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        full_response = ""
        usage_data = None  # Will capture token usage from AI response

        try:
            # Send session_id first
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

            # Send user message ID and token count so frontend can display
            yield f"data: {json.dumps({'type': 'user_message_id', 'message_id': user_msg.id, 'input_tokens': user_input_tokens, 'tokens_estimated': True})}\n\n"

            # Stream AI response (pass RAG context and age-based system prompt if available)
            for chunk in AIService.get_response_stream(messages, model_provider, model_name, user_id, upload_folder, rag_context, age_system_prompt, local_vision_enabled):
                # Parse the SSE chunk to get the JSON data
                if chunk.startswith('data: '):
                    chunk_data = json.loads(chunk[6:])

                    # Track full content
                    if chunk_data.get('type') == 'content':
                        full_response += chunk_data.get('content', '')
                    elif chunk_data.get('type') == 'done':
                        full_response = chunk_data.get('full_content', full_response)
                        # Capture usage data from the done event
                        usage_data = chunk_data.get('usage')

                # Forward the chunk to client
                yield chunk

            # Save bot response to database after streaming completes
            if full_response:
                # Extract token counts from usage data
                output_tokens = 0
                tokens_estimated = True
                if usage_data:
                    output_tokens = usage_data.get('output_tokens', 0)
                    tokens_estimated = usage_data.get('estimated', True)

                bot_msg = Message(
                    chat_id=chat.id,
                    role="assistant",
                    content=full_response,
                    model_used=model_name or model_provider,
                    output_tokens=output_tokens,
                    tokens_used=output_tokens,
                    tokens_estimated=tokens_estimated
                )
                db.session.add(bot_msg)

                # Update chat timestamp
                from datetime import datetime
                chat.updated_at = datetime.utcnow()

                db.session.commit()

                # Distilled Context: Generate summaries if enabled
                from app.models.admin_settings import AdminSettings
                if AdminSettings.is_distilled_context_enabled():
                    _generate_distilled_context(
                        user_msg=user_msg,
                        bot_msg=bot_msg,
                        user_message_content=message_content,
                        bot_response=full_response,
                        model_provider=model_provider,
                        model_name=model_name,
                        user_id=user_id,
                        upload_folder=upload_folder
                    )

                # Send bot message ID and token count so frontend can display
                yield f"data: {json.dumps({'type': 'bot_message_id', 'message_id': bot_msg.id, 'output_tokens': output_tokens, 'tokens_estimated': tokens_estimated})}\n\n"

        except Exception as e:
            current_app.logger.error(f"Streaming error: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
        }
    )


@bp.route('/history', methods=['GET'])
@login_required
def get_history():
    """Retrieve chat history for a session - requires authentication"""
    session_id = request.args.get("session_id")

    if not session_id:
        return jsonify({"error": "No session_id provided"}), 400

    chat = Chat.query.filter_by(session_id=session_id).first()
    if not chat:
        return jsonify({"error": "Session not found"}), 404

    # Check permissions - user can only access their own chats
    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    history = [msg.to_dict() for msg in chat.messages.all()]
    return jsonify(history)


@bp.route('/sessions', methods=['GET'])
@login_required
def get_sessions():
    """
    Retrieve all chat sessions for the authenticated user
    """
    chats = Chat.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Chat.updated_at.desc()).all()

    sessions = [
        {
            "session_id": chat.session_id,
            "name": chat.name,
            "model_provider": chat.model_provider,
            "created_at": chat.created_at.isoformat() + 'Z' if chat.created_at else None,
            "updated_at": chat.updated_at.isoformat() + 'Z' if chat.updated_at else None
        }
        for chat in chats
    ]

    return jsonify(sessions)


@bp.route('/delete_chat/<session_id>', methods=['DELETE'])
@login_required
def delete_chat(session_id):
    """Delete a chat session and all associated files - requires authentication"""
    chat = Chat.query.filter_by(session_id=session_id).first()

    if not chat:
        return jsonify({"error": "Session not found"}), 404

    # Check permissions - user can only delete their own chats
    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Delete all associated files before deleting database records
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)

        deleted_files = 0
        failed_files = 0

        # Get all messages in the chat
        messages = chat.messages.all()

        # For each message, delete all attachment files
        for message in messages:
            for attachment in message.attachments:
                if file_service.delete_file(attachment.file_path):
                    deleted_files += 1
                else:
                    failed_files += 1

        # Now delete the chat from database (cascade will handle messages and attachments)
        db.session.delete(chat)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Chat deleted successfully",
            "files_deleted": deleted_files,
            "files_failed": failed_files
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete chat: {str(e)}"}), 500


@bp.route('/messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    """Delete a specific message and its attachments - requires authentication"""
    message = Message.query.get_or_404(message_id)
    chat = message.chat

    # Verify ownership - user can only delete messages from their own chats
    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Delete attachment files from disk first
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)

        deleted_files = 0
        for attachment in message.attachments:
            if file_service.delete_file(attachment.file_path):
                deleted_files += 1

        # Delete message from DB (cascade handles attachments in DB)
        db.session.delete(message)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Message deleted",
            "files_deleted": deleted_files
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete message {message_id}: {str(e)}")
        return jsonify({"error": f"Failed to delete message: {str(e)}"}), 500


@bp.route('/rename_chat/<session_id>', methods=['PUT'])
@login_required
def rename_chat(session_id):
    """Rename a chat session - requires authentication"""
    chat = Chat.query.filter_by(session_id=session_id).first()

    if not chat:
        return jsonify({"error": "Session not found"}), 404

    # Check permissions - user can only rename their own chats
    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Get new name from request
    data = request.get_json()
    new_name = data.get('name', '').strip()

    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400

    # Update chat name
    chat.name = new_name
    db.session.commit()

    return jsonify({"status": "success", "message": "Chat renamed", "name": new_name})


@bp.route('/export_chat/<session_id>', methods=['GET'])
@login_required
def export_chat(session_id):
    """Export a chat session to a text file - requires authentication"""
    chat = Chat.query.filter_by(session_id=session_id).first()

    if not chat:
        return jsonify({"error": "Session not found"}), 404

    # Check permissions - user can only export their own chats
    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Build the text content
        from datetime import datetime
        import io

        output = io.StringIO()

        # Write header
        output.write(f"Chat Export: {chat.name}\n")
        output.write(f"Exported on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        output.write(f"Model: {chat.model_provider or 'Unknown'}\n")
        output.write("=" * 80 + "\n\n")

        # Write messages
        messages = chat.messages.order_by(Message.created_at).all()

        for message in messages:
            # Format timestamp
            timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

            # Format role
            role = "You" if message.role == "user" else message.model_used or "Assistant"

            # Write message header
            output.write(f"[{timestamp}] {role}:\n")

            # Write content (excluding attachments - text only)
            # Remove thinking tags if present
            content = message.content
            if message.role in ['bot', 'assistant']:
                # Remove thinking content from export
                import re
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            output.write(f"{content}\n")

            # Add separator between messages
            output.write("\n" + "-" * 80 + "\n\n")

        # Get the text content
        text_content = output.getvalue()
        output.close()

        # Create a file-like object for send_file
        file_obj = io.BytesIO(text_content.encode('utf-8'))

        # Generate filename
        safe_filename = "".join(c for c in chat.name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_filename = safe_filename[:50]  # Limit length
        filename = f"{safe_filename}_{datetime.utcnow().strftime('%Y%m%d')}.txt"

        return send_file(
            file_obj,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Error exporting chat {session_id}: {str(e)}")
        return jsonify({"error": f"Failed to export chat: {str(e)}"}), 500


@bp.route('/export_all_chats', methods=['GET'])
@login_required
def export_all_chats():
    """Export all chat sessions for the authenticated user as a zip file"""
    try:
        # Get all non-deleted chats for the current user
        chats = Chat.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Chat.updated_at.desc()).all()

        if not chats:
            return jsonify({"error": "No chats to export"}), 404

        # Create a BytesIO buffer for the zip file
        zip_buffer = io.BytesIO()

        # Create zip file
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for chat in chats:
                # Build text content for each chat
                output = io.StringIO()

                # Write header
                output.write(f"Chat Export: {chat.name}\n")
                output.write(f"Exported on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
                output.write(f"Model: {chat.model_provider or 'Unknown'}\n")
                output.write("=" * 80 + "\n\n")

                # Write messages
                messages = chat.messages.order_by(Message.created_at).all()

                for message in messages:
                    # Format timestamp
                    timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

                    # Format role
                    role = "You" if message.role == "user" else message.model_used or "Assistant"

                    # Write message header
                    output.write(f"[{timestamp}] {role}:\n")

                    # Write content (excluding thinking tags)
                    content = message.content
                    if message.role in ['bot', 'assistant']:
                        # Remove thinking content from export
                        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

                    output.write(f"{content}\n")

                    # Add separator between messages
                    output.write("\n" + "-" * 80 + "\n\n")

                # Get the text content
                text_content = output.getvalue()
                output.close()

                # Generate safe filename for this chat
                safe_filename = "".join(c for c in chat.name if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_filename = safe_filename[:50]  # Limit length

                # Add index number to ensure uniqueness
                chat_index = chats.index(chat) + 1
                filename = f"{chat_index:03d}_{safe_filename}.txt"

                # Add file to zip
                zip_file.writestr(filename, text_content.encode('utf-8'))

        # Seek to beginning of the buffer
        zip_buffer.seek(0)

        # Generate zip filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"Exported_Chats_{timestamp}.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        current_app.logger.error(f"Error exporting all chats: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to export chats: {str(e)}"}), 500


@bp.route('/config', methods=['GET'])
@login_required
def get_config():
    """Get API configuration (masked system keys and model IDs) - super_admin only"""
    from app.models.admin_settings import AdminSettings

    # Only super_admin can view system API keys
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    # Get system API keys status from AdminSettings
    api_keys_status = AdminSettings.get_all_system_api_keys_status()

    # Get system model settings from AdminSettings
    model_settings = AdminSettings.get_all_system_model_settings()

    return jsonify({
        # API Keys (masked)
        "gemini_api_key": api_keys_status['gemini']['masked_key'],
        "openai_api_key": api_keys_status['openai']['masked_key'],
        "anthropic_api_key": api_keys_status['anthropic']['masked_key'],
        "xai_api_key": api_keys_status['xai']['masked_key'],
        "has_gemini": api_keys_status['gemini']['configured'],
        "has_openai": api_keys_status['openai']['configured'],
        "has_anthropic": api_keys_status['anthropic']['configured'],
        "has_xai": api_keys_status['xai']['configured'],
        # Model IDs
        "gemini_model_id": model_settings.get('gemini_model_id', ''),
        "openai_model_id": model_settings.get('openai_model_id', ''),
        "anthropic_model_id": model_settings.get('anthropic_model_id', ''),
        "xai_model_id": model_settings.get('xai_model_id', ''),
        # Local model settings
        "lm_studio_url": model_settings.get('lm_studio_url', ''),
        "lm_studio_model_id": model_settings.get('lm_studio_model_id', ''),
        "ollama_url": model_settings.get('ollama_url', ''),
        "ollama_model_id": model_settings.get('ollama_model_id', ''),
        "note": "System API keys are stored encrypted in the database. Model IDs are stored in plain text."
    })


@bp.route('/config', methods=['POST'])
@login_required
def save_config():
    """
    Save system API key and model ID configuration - super_admin only
    Stores encrypted API keys and plain text model IDs in AdminSettings (system-level)
    """
    from app.models.admin_settings import AdminSettings

    # Only super_admin can modify system API keys
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    updated_items = []
    errors = []

    # Map of field names to provider names for API keys
    api_key_map = {
        'gemini_api_key': 'gemini',
        'openai_api_key': 'openai',
        'anthropic_api_key': 'anthropic',
        'xai_api_key': 'xai'
    }

    # Process API keys
    for field_name, provider_name in api_key_map.items():
        if field_name in data:
            api_key_value = data[field_name].strip()

            if not api_key_value:
                # Delete existing key if empty string provided
                if AdminSettings.has_system_api_key(provider_name):
                    if AdminSettings.set_system_api_key(provider_name, ''):
                        updated_items.append(f"{provider_name} API key (removed)")
                    else:
                        errors.append(f"{provider_name}: Failed to remove key")
                continue

            # Validate API key format
            if len(api_key_value) < 10:
                errors.append(f"{provider_name}: API key too short")
                continue

            try:
                if AdminSettings.set_system_api_key(provider_name, api_key_value):
                    updated_items.append(f"{provider_name} API key")
                else:
                    errors.append(f"{provider_name}: Failed to save key")
            except Exception as e:
                errors.append(f"{provider_name}: {str(e)}")

    # Map of field names to provider names for model IDs
    model_id_map = {
        'gemini_model_id': 'gemini',
        'openai_model_id': 'openai',
        'anthropic_model_id': 'anthropic',
        'xai_model_id': 'xai',
        'lm_studio_model_id': 'lm_studio',
        'ollama_model_id': 'ollama'
    }

    # Process model IDs
    for field_name, provider_name in model_id_map.items():
        if field_name in data:
            model_id_value = data[field_name].strip() if data[field_name] else ''

            try:
                if AdminSettings.set_system_model_id(provider_name, model_id_value):
                    updated_items.append(f"{provider_name} model ID")
                else:
                    errors.append(f"{provider_name}: Failed to save model ID")
            except Exception as e:
                errors.append(f"{provider_name} model ID: {str(e)}")

    # Map of field names to provider names for local model URLs
    url_map = {
        'lm_studio_url': 'lm_studio',
        'ollama_url': 'ollama'
    }

    # Process local model URLs
    for field_name, provider_name in url_map.items():
        if field_name in data:
            url_value = data[field_name].strip() if data[field_name] else ''

            try:
                if AdminSettings.set_local_model_url(provider_name, url_value):
                    updated_items.append(f"{provider_name} URL")
                else:
                    errors.append(f"{provider_name}: Failed to save URL")
            except Exception as e:
                errors.append(f"{provider_name} URL: {str(e)}")

    if not updated_items and not errors:
        return jsonify({"error": "No configuration provided"}), 400

    response_data = {
        "status": "success" if not errors else "partial_success",
        "message": f"Updated: {', '.join(updated_items)}" if updated_items else "No settings updated"
    }

    if errors:
        response_data["errors"] = errors

    return jsonify(response_data)


@bp.route('/upload_attachment', methods=['POST'])
@login_required
@limiter.limit(rate_limit_attachment_upload)
def upload_attachment():
    """
    Upload a file attachment (image or document) - requires authentication.
    Returns attachment info that can be included when sending a message.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']

    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        # Initialize file service
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)

        # Save file
        file_info, error = file_service.save_file(file)

        if error:
            return jsonify({"error": error}), 400

        # Return file info (attachment will be created when message is sent)
        return jsonify({
            "status": "success",
            "file_info": {
                "original_filename": file_info['original_filename'],
                "stored_filename": file_info['stored_filename'],
                "file_path": file_info['file_path'],
                "file_type": file_info['file_type'],
                "mime_type": file_info['mime_type'],
                "file_size": file_info['file_size'],
                "file_size_formatted": FileService.format_file_size(file_info['file_size'])
            }
        }), 200

    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@bp.route('/attachments/<int:attachment_id>', methods=['GET'])
@login_required
def get_attachment(attachment_id):
    """
    Retrieve and serve an attachment file - requires authentication.
    Supports both viewing and downloading.
    """
    attachment = Attachment.query.get_or_404(attachment_id)

    # Check permissions - user can only access their own attachments
    message = attachment.message
    chat = message.chat

    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Get file path
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_path = file_service.get_file_path(attachment.file_path)

        if not file_path:
            return jsonify({"error": "File not found"}), 404

        # Determine if we should display inline or as download
        as_attachment = request.args.get('download', 'false').lower() == 'true'

        return send_file(
            str(file_path),  # Convert Path object to string
            mimetype=attachment.mime_type,
            as_attachment=as_attachment,
            download_name=attachment.original_filename
        )

    except Exception as e:
        current_app.logger.error(f"Error retrieving attachment {attachment_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve file"}), 500


@bp.route('/attachments/<int:attachment_id>', methods=['DELETE'])
@login_required
def delete_attachment(attachment_id):
    """
    Delete an attachment - requires authentication.
    Only the message owner can delete attachments.
    """
    attachment = Attachment.query.get_or_404(attachment_id)

    # Check permissions - user can only delete their own attachments
    message = attachment.message
    chat = message.chat

    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Delete file from storage
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_service.delete_file(attachment.file_path)

        # Delete from database
        db.session.delete(attachment)
        db.session.commit()

        return jsonify({"status": "success", "message": "Attachment deleted"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete attachment: {str(e)}"}), 500


# Admin endpoints for model visibility management
@bp.route('/admin/models', methods=['GET'])
@login_required
def get_admin_models():
    """
    Get all models with visibility status (super_admin only).
    Returns all models for admin configuration.
    """
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.model_visibility import ModelVisibility
        models = ModelVisibility.get_all_models()
        return jsonify({
            "status": "success",
            "models": models
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve models: {str(e)}"}), 500


@bp.route('/admin/models/<int:model_id>', methods=['PUT'])
@login_required
def update_model_visibility(model_id):
    """
    Update model visibility settings (super_admin only).
    Allows toggling whether a model is visible to users.
    """
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.model_visibility import ModelVisibility

        model = ModelVisibility.query.get_or_404(model_id)

        data = request.get_json()
        if 'is_enabled' not in data:
            return jsonify({"error": "is_enabled field is required"}), 400

        model.is_enabled = bool(data['is_enabled'])
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Model {model.display_name} visibility updated",
            "model": model.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update model: {str(e)}"}), 500


@bp.route('/models/enabled', methods=['GET'])
@login_required
def get_enabled_models():
    """
    Get list of enabled models for authenticated users.
    Used by the frontend to populate model dropdown.
    """
    try:
        from app.models.model_visibility import ModelVisibility
        models = ModelVisibility.get_enabled_models()
        return jsonify({
            "status": "success",
            "models": models
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve models: {str(e)}"}), 500


# Admin settings endpoints
@bp.route('/admin/settings', methods=['GET'])
@login_required
def get_admin_settings():
    """
    Get all admin settings (super_admin only).
    """
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.admin_settings import AdminSettings
        settings = AdminSettings.query.all()
        return jsonify({
            "status": "success",
            "settings": [s.to_dict() for s in settings]
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve settings: {str(e)}"}), 500


@bp.route('/admin/settings/<setting_key>', methods=['GET'])
@login_required
def get_admin_setting(setting_key):
    """
    Get a specific admin setting (super_admin only).
    """
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.admin_settings import AdminSettings
        setting = AdminSettings.query.filter_by(setting_key=setting_key).first()

        if not setting:
            return jsonify({"error": "Setting not found"}), 404

        return jsonify({
            "status": "success",
            "setting": setting.to_dict()
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve setting: {str(e)}"}), 500


@bp.route('/admin/settings/<setting_key>', methods=['PUT'])
@login_required
def update_admin_setting(setting_key):
    """
    Update a specific admin setting (super_admin only).
    """
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.admin_settings import AdminSettings

        data = request.get_json()
        if 'value' not in data:
            return jsonify({"error": "value field is required"}), 400

        # Get or create the setting
        setting = AdminSettings.query.filter_by(setting_key=setting_key).first()

        if not setting:
            # Create new setting if it doesn't exist
            setting_type = data.get('setting_type', 'string')
            description = data.get('description', '')

            setting = AdminSettings(
                setting_key=setting_key,
                setting_type=setting_type,
                description=description
            )
            db.session.add(setting)

        # Update the value
        setting.set_typed_value(data['value'])
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Setting '{setting_key}' updated successfully",
            "setting": setting.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update setting: {str(e)}"}), 500


# =============================================================================
# Rate Limit Settings Endpoints (Admin Only)
# =============================================================================

@bp.route('/admin/rate-limits', methods=['GET'])
@login_required
def get_rate_limits():
    """
    Get all rate limit settings (super_admin only).
    """
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.admin_settings import AdminSettings
        rate_limits = AdminSettings.get_all_rate_limits()
        return jsonify({
            "status": "success",
            "rate_limits": rate_limits
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve rate limits: {str(e)}"}), 500


@bp.route('/admin/rate-limits', methods=['PUT'])
@login_required
def update_rate_limits():
    """
    Update rate limit settings (super_admin only).
    Accepts JSON with rate limit values.
    """
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    try:
        from app.models.admin_settings import AdminSettings

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        updated = []
        errors = []

        # Handle enabled toggle
        if 'enabled' in data:
            try:
                AdminSettings.set_setting(
                    key='rate_limit_enabled',
                    value=bool(data['enabled']),
                    setting_type='boolean',
                    description='Enable rate limiting for all endpoints'
                )
                updated.append('enabled')
            except Exception as e:
                errors.append(f"Failed to update enabled: {str(e)}")

        # Handle individual rate limits
        for limit_name in AdminSettings.DEFAULT_RATE_LIMITS.keys():
            if limit_name in data:
                try:
                    value = int(data[limit_name])
                    if value < 1:
                        errors.append(f"{limit_name}: Value must be at least 1")
                        continue
                    if value > 10000:
                        errors.append(f"{limit_name}: Value cannot exceed 10000")
                        continue
                    AdminSettings.set_rate_limit(limit_name, value)
                    updated.append(limit_name)
                except (ValueError, TypeError):
                    errors.append(f"{limit_name}: Invalid value")

        if errors and not updated:
            return jsonify({"error": "Failed to update rate limits", "details": errors}), 400

        return jsonify({
            "status": "success",
            "message": f"Updated {len(updated)} rate limit setting(s)",
            "updated": updated,
            "errors": errors if errors else None,
            "rate_limits": AdminSettings.get_all_rate_limits()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update rate limits: {str(e)}"}), 500


# =============================================================================
# Available Models Endpoint (Admin Only)
# =============================================================================

def _get_cached_models(provider):
    """Get cached model list if still valid."""
    if provider in _model_list_cache:
        cached = _model_list_cache[provider]
        if time.time() - cached['timestamp'] < MODEL_CACHE_TTL:
            return cached['models']
    return None


def _set_cached_models(provider, models):
    """Cache model list for a provider."""
    _model_list_cache[provider] = {
        'models': models,
        'timestamp': time.time()
    }


def _fetch_ollama_models(base_url):
    """Fetch models from Ollama API."""
    # Convert chat URL to tags URL
    tags_url = base_url.replace('/api/chat', '').rstrip('/') + '/api/tags'

    response = http_requests.get(tags_url, timeout=5)
    response.raise_for_status()
    data = response.json()

    models = []
    for model in data.get('models', []):
        model_name = model.get('name', '')
        if model_name:
            models.append({
                'id': model_name,
                'name': model_name
            })
    return models


def _fetch_lm_studio_models(base_url):
    """Fetch models from LM Studio API (OpenAI-compatible)."""
    # Convert chat URL to models URL
    models_url = base_url.replace('/v1/chat/completions', '').rstrip('/') + '/v1/models'

    response = http_requests.get(models_url, timeout=5)
    response.raise_for_status()
    data = response.json()

    models = []
    for model in data.get('data', []):
        model_id = model.get('id', '')
        if model_id:
            models.append({
                'id': model_id,
                'name': model_id
            })
    return models


def _fetch_openai_models(api_key):
    """Fetch models from OpenAI API."""
    response = http_requests.get(
        'https://api.openai.com/v1/models',
        headers={'Authorization': f'Bearer {api_key}'},
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    models = []
    for model in data.get('data', []):
        model_id = model.get('id', '')
        # Filter to chat-capable models (gpt, o1, o3, chatgpt)
        if model_id and any(prefix in model_id.lower() for prefix in ['gpt', 'o1', 'o3', 'chatgpt']):
            models.append({
                'id': model_id,
                'name': model_id
            })
    # Sort by model ID
    models.sort(key=lambda x: x['id'])
    return models


def _fetch_anthropic_models(api_key):
    """Fetch models from Anthropic API."""
    response = http_requests.get(
        'https://api.anthropic.com/v1/models',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01'
        },
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    models = []
    for model in data.get('data', []):
        model_id = model.get('id', '')
        display_name = model.get('display_name', model_id)
        if model_id:
            models.append({
                'id': model_id,
                'name': display_name if display_name != model_id else model_id
            })
    return models


def _fetch_gemini_models(api_key):
    """Fetch models from Gemini API."""
    response = http_requests.get(
        f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}',
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    models = []
    for model in data.get('models', []):
        # Only include models that support generateContent
        supported_methods = model.get('supportedGenerationMethods', [])
        if 'generateContent' in supported_methods:
            # Model name comes as "models/gemini-pro" - strip the prefix
            full_name = model.get('name', '')
            model_id = full_name.replace('models/', '') if full_name.startswith('models/') else full_name
            display_name = model.get('displayName', model_id)
            if model_id:
                models.append({
                    'id': model_id,
                    'name': display_name if display_name != model_id else model_id
                })
    return models


def _fetch_xai_models(api_key):
    """Fetch models from xAI API (OpenAI-compatible)."""
    response = http_requests.get(
        'https://api.x.ai/v1/models',
        headers={'Authorization': f'Bearer {api_key}'},
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    models = []
    for model in data.get('data', []):
        model_id = model.get('id', '')
        if model_id:
            models.append({
                'id': model_id,
                'name': model_id
            })
    return models


@bp.route('/admin/available-models/<provider>', methods=['GET'])
@login_required
def get_available_models(provider):
    """
    Fetch available models from a provider's API (super_admin only).
    Returns list of model IDs that can be used for the dropdown selector.

    Supported providers: ollama, lm_studio, openai, anthropic, gemini, xai
    """
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        return jsonify({"error": "Unauthorized. Super admin access required."}), 403

    # Validate provider
    valid_providers = ['ollama', 'lm_studio', 'openai', 'anthropic', 'gemini', 'xai']
    if provider not in valid_providers:
        return jsonify({
            "status": "error",
            "error": "invalid_provider",
            "message": f"Invalid provider. Must be one of: {', '.join(valid_providers)}",
            "allow_manual_entry": True
        })

    # Check cache first (unless force refresh requested)
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    if not force_refresh:
        cached = _get_cached_models(provider)
        if cached is not None:
            return jsonify({
                "status": "success",
                "provider": provider,
                "models": cached,
                "cached": True
            })

    from app.models.admin_settings import AdminSettings

    try:
        models = []

        if provider == 'ollama':
            base_url = AdminSettings.get_local_model_url('ollama')
            if not base_url:
                base_url = 'http://localhost:11434/api/chat'
            models = _fetch_ollama_models(base_url)

        elif provider == 'lm_studio':
            base_url = AdminSettings.get_local_model_url('lm_studio')
            if not base_url:
                base_url = 'http://localhost:1234/v1/chat/completions'
            models = _fetch_lm_studio_models(base_url)

        elif provider == 'openai':
            api_key = AdminSettings.get_system_api_key('openai')
            if not api_key:
                return jsonify({
                    "status": "error",
                    "error": "api_key_not_configured",
                    "message": "OpenAI API key is not configured",
                    "allow_manual_entry": True
                })
            models = _fetch_openai_models(api_key)

        elif provider == 'anthropic':
            api_key = AdminSettings.get_system_api_key('anthropic')
            if not api_key:
                return jsonify({
                    "status": "error",
                    "error": "api_key_not_configured",
                    "message": "Anthropic API key is not configured",
                    "allow_manual_entry": True
                })
            models = _fetch_anthropic_models(api_key)

        elif provider == 'gemini':
            api_key = AdminSettings.get_system_api_key('gemini')
            if not api_key:
                return jsonify({
                    "status": "error",
                    "error": "api_key_not_configured",
                    "message": "Gemini API key is not configured",
                    "allow_manual_entry": True
                })
            models = _fetch_gemini_models(api_key)

        elif provider == 'xai':
            api_key = AdminSettings.get_system_api_key('xai')
            if not api_key:
                return jsonify({
                    "status": "error",
                    "error": "api_key_not_configured",
                    "message": "xAI API key is not configured",
                    "allow_manual_entry": True
                })
            models = _fetch_xai_models(api_key)

        # Cache the results
        _set_cached_models(provider, models)

        return jsonify({
            "status": "success",
            "provider": provider,
            "models": models,
            "cached": False
        })

    except http_requests.exceptions.ConnectionError as e:
        error_msg = f"Could not connect to {provider}"
        if provider in ['ollama', 'lm_studio']:
            error_msg += f". Please ensure {provider.replace('_', ' ').title()} is running."
        return jsonify({
            "status": "error",
            "error": "connection_error",
            "message": error_msg,
            "allow_manual_entry": True
        })

    except http_requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "error": "timeout",
            "message": f"Request to {provider} timed out",
            "allow_manual_entry": True
        })

    except http_requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 'unknown'
        if status_code == 401:
            return jsonify({
                "status": "error",
                "error": "authentication_failed",
                "message": f"Authentication failed for {provider}. Please check your API key.",
                "allow_manual_entry": True
            })
        return jsonify({
            "status": "error",
            "error": "http_error",
            "message": f"HTTP error {status_code} from {provider}",
            "allow_manual_entry": True
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching models from {provider}: {str(e)}")
        return jsonify({
            "status": "error",
            "error": "unknown_error",
            "message": f"Failed to fetch models from {provider}",
            "allow_manual_entry": True
        })


# =============================================================================
# RAG Document Management Endpoints
# =============================================================================

@bp.route('/documents', methods=['GET'])
@login_required
def list_documents():
    """
    List all RAG documents for the current user.
    Optional query param: project_id to filter by project.
    """
    try:
        project_id = request.args.get('project_id', type=int)
        documents = RAGService.get_user_documents(current_user.id, project_id)

        return jsonify({
            "status": "success",
            "documents": documents,
            "count": len(documents)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to list documents: {str(e)}"}), 500


@bp.route('/documents', methods=['POST'])
@login_required
@limiter.limit(rate_limit_document_upload)
def upload_document():
    """
    Upload a document for RAG processing.
    The document will be processed (extracted, chunked, embedded) after upload.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    project_id = request.form.get('project_id', type=int)

    try:
        # Upload and process the document
        result = RAGService.upload_and_process(
            user_id=current_user.id,
            file=file,
            project_id=project_id
        )

        if result.get('success'):
            return jsonify({
                "status": "success",
                "message": "Document uploaded and processed successfully",
                "document_id": result.get('document_id'),
                "chunk_count": result.get('chunk_count'),
                "total_tokens": result.get('total_tokens')
            }), 201
        else:
            return jsonify({
                "status": "error",
                "error": result.get('error', 'Unknown error')
            }), 400

    except Exception as e:
        current_app.logger.error(f"Document upload error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@bp.route('/documents/<int:document_id>', methods=['GET'])
@login_required
def get_document(document_id):
    """
    Get details for a specific document.
    """
    document = Document.query.get_or_404(document_id)

    # Check ownership
    if document.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "status": "success",
        "document": document.to_dict()
    })


@bp.route('/documents/<int:document_id>', methods=['DELETE'])
@login_required
def delete_document(document_id):
    """
    Delete a document and all its associated data (chunks, embeddings).
    """
    document = Document.query.get_or_404(document_id)

    # Check ownership
    if document.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        result = RAGService.delete_document(document_id)

        if result.get('success'):
            return jsonify({
                "status": "success",
                "message": "Document deleted successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "error": result.get('error', 'Delete failed')
            }), 500

    except Exception as e:
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500


@bp.route('/documents/<int:document_id>/reprocess', methods=['POST'])
@login_required
def reprocess_document(document_id):
    """
    Reprocess a document (useful if processing failed or settings changed).
    """
    document = Document.query.get_or_404(document_id)

    # Check ownership
    if document.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        result = RAGService.process_document(document_id)

        if result.get('success'):
            return jsonify({
                "status": "success",
                "message": "Document reprocessed successfully",
                "chunk_count": result.get('chunk_count'),
                "total_tokens": result.get('total_tokens')
            })
        else:
            return jsonify({
                "status": "error",
                "error": result.get('error', 'Processing failed')
            }), 500

    except Exception as e:
        return jsonify({"error": f"Reprocessing failed: {str(e)}"}), 500


@bp.route('/documents/search', methods=['POST'])
@login_required
def search_documents():
    """
    Search across user's documents using semantic search.
    """
    data = request.get_json()
    query = data.get('query', '').strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400

    top_k = data.get('top_k', 5)
    min_score = data.get('min_score', 0.7)
    document_ids = data.get('document_ids')  # Optional: filter by specific documents

    try:
        results = RAGService.retrieve_context(
            user_id=current_user.id,
            query=query,
            top_k=top_k,
            min_score=min_score,
            document_ids=document_ids
        )

        return jsonify({
            "status": "success",
            "query": query,
            "results": results,
            "count": len(results)
        })

    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500


@bp.route('/documents/stats', methods=['GET'])
@login_required
def get_document_stats():
    """
    Get RAG statistics for the current user.
    """
    try:
        from app.services.vector_store import VectorStore

        # Get document counts by status
        total_docs = Document.query.filter_by(user_id=current_user.id).count()
        ready_docs = Document.query.filter_by(user_id=current_user.id, status='ready').count()
        pending_docs = Document.query.filter_by(user_id=current_user.id, status='pending').count()
        processing_docs = Document.query.filter_by(user_id=current_user.id, status='processing').count()
        failed_docs = Document.query.filter_by(user_id=current_user.id, status='failed').count()

        # Get total chunks and tokens
        from sqlalchemy import func
        stats = db.session.query(
            func.sum(Document.chunk_count).label('total_chunks'),
            func.sum(Document.total_tokens).label('total_tokens')
        ).filter_by(user_id=current_user.id, status='ready').first()

        # Get vector store stats
        vector_stats = VectorStore.get_collection_stats(current_user.id)

        # Get settings
        settings = RAGService.get_settings()

        return jsonify({
            "status": "success",
            "stats": {
                "documents": {
                    "total": total_docs,
                    "ready": ready_docs,
                    "pending": pending_docs,
                    "processing": processing_docs,
                    "failed": failed_docs
                },
                "chunks": {
                    "total": stats.total_chunks or 0,
                    "in_vector_store": vector_stats.get('count', 0)
                },
                "tokens": {
                    "total": stats.total_tokens or 0
                },
                "limits": {
                    "max_documents": settings.get('rag_max_documents_per_user', 50),
                    "remaining": max(0, settings.get('rag_max_documents_per_user', 50) - total_docs)
                },
                "rag_enabled": settings.get('rag_enabled', True)
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting document stats: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get stats: {str(e)}"}), 500


@bp.route('/rag/settings', methods=['GET'])
@login_required
def get_rag_settings():
    """
    Get RAG settings for the current user.
    """
    try:
        settings = RAGService.get_settings()
        can_upload, reason = RAGService.can_upload_document(current_user.id)

        return jsonify({
            "status": "success",
            "settings": settings,
            "can_upload": can_upload,
            "upload_blocked_reason": reason
        })

    except Exception as e:
        return jsonify({"error": f"Failed to get settings: {str(e)}"}), 500


# =============================================================================
# Prompt Improvement Endpoint
# =============================================================================

@bp.route('/improve_prompt', methods=['POST'])
@login_required
@limiter.limit(rate_limit_improve_prompt)
def improve_prompt():
    """
    Use AI to improve/enhance a user prompt - requires authentication.
    Returns a complete (non-streaming) response with the improved prompt.
    """
    data = request.get_json()

    original_prompt = data.get("prompt", "").strip()
    model_provider = data.get("model", "gemini")
    local_model_provider = data.get("local_model_provider", "lmstudio")

    if not original_prompt:
        return jsonify({"error": "No prompt provided"}), 400

    if len(original_prompt) > 10000:
        return jsonify({"error": "Prompt too long (max 10,000 characters)"}), 400

    # Map old model names to new provider names
    if model_provider == "simply":
        model_provider = local_model_provider

    # System prompt for improving the user's prompt
    system_prompt = """You are a prompt engineering expert. Your ONLY job is to rewrite and improve prompts that users give you. You must NEVER answer or respond to the content of the prompt itself.

CRITICAL RULES:
- You must OUTPUT ONLY the rewritten/improved version of the prompt
- Do NOT answer the question in the prompt
- Do NOT provide information about the topic in the prompt
- Do NOT include explanations, headers, commentary, or preamble
- Do NOT include markdown formatting like ### headers in your output
- The user's prompt is a PROMPT TO BE REWRITTEN, not a question for you to answer

Guidelines for improving prompts:
1. Add clarity and specificity where the original is vague
2. Include relevant context that might be missing
3. Structure the request logically
4. Add any helpful constraints or format requirements
5. Preserve the original intent and meaning
6. Keep the improved prompt concise but comprehensive

Example:
- Input prompt: "why is the sky blue?"
- Improved prompt: "Explain why the sky appears blue during the day. Include the scientific principles involved such as light scattering, and describe how different wavelengths of light interact with Earth's atmosphere. Keep the explanation accessible to someone without a physics background."

Remember: Output ONLY the improved prompt text. Nothing else."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Rewrite and improve the following prompt (do NOT answer it, just improve it as a prompt):\n\n---\n{original_prompt}\n---"}
    ]

    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        result = AIService.get_response(
            messages=messages,
            provider=model_provider,
            model_name=None,
            user_id=current_user.id,
            upload_folder=upload_folder
        )

        if result.get('error'):
            return jsonify({"error": result['error']}), 500

        # Strip thinking tags from reasoning models before returning
        improved = re.sub(r'<think>.*?</think>', '', result.get('response', ''), flags=re.DOTALL).strip()

        return jsonify({
            "status": "success",
            "improved_prompt": improved
        })

    except Exception as e:
        current_app.logger.error(f"Improve prompt error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to improve prompt: {str(e)}"}), 500
