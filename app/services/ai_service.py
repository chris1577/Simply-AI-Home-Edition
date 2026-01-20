import requests
import base64
import os
import json
from pathlib import Path
from flask import current_app
from typing import List, Dict, Any, Optional, Generator
from google import genai
from google.genai import types


class AIService:
    """Service layer for AI model interactions"""

    @staticmethod
    def _encode_image_to_base64(file_path: str) -> Optional[str]:
        """
        Encode an image file to base64 string.

        Args:
            file_path: Path to the image file

        Returns:
            Base64 encoded string or None if error
        """
        try:
            with open(file_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            current_app.logger.error(f"Error encoding image {file_path}: {str(e)}")
            return None

    @staticmethod
    def _get_attachment_content(attachment: Dict[str, Any], upload_folder: str) -> Optional[Dict[str, Any]]:
        """
        Get attachment content for AI processing.
        Uses DocumentExtractor to extract text from PDFs, DOCX, XLSX files.

        Args:
            attachment: Attachment metadata dict
            upload_folder: Base upload folder path

        Returns:
            Dict with attachment data or None if error
        """
        try:
            file_path = Path(upload_folder) / attachment['file_path']
            if not file_path.exists():
                current_app.logger.error(f"Attachment file not found: {file_path}")
                return None

            mime_type = attachment['mime_type']
            file_type = attachment['file_type']
            filename = attachment['original_filename']

            # For images, encode as base64
            if file_type == 'image':
                base64_data = AIService._encode_image_to_base64(str(file_path))
                if base64_data:
                    return {
                        'type': 'image',
                        'mime_type': mime_type,
                        'base64': base64_data,
                        'filename': filename
                    }

            # For documents, extract text using DocumentExtractor
            elif file_type == 'document':
                # Plain text files - read directly
                if mime_type in ['text/plain', 'text/csv', 'text/markdown', 'application/json']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            text_content = f.read()
                    except UnicodeDecodeError:
                        with open(file_path, 'r', encoding='latin-1') as f:
                            text_content = f.read()
                    return {
                        'type': 'text_document',
                        'mime_type': mime_type,
                        'content': text_content,
                        'filename': filename
                    }

                # PDFs, DOCX, XLSX - use DocumentExtractor to get text
                elif mime_type in [
                    'application/pdf',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'application/msword',
                    'application/vnd.ms-excel'
                ]:
                    try:
                        from app.services.document_extractor import DocumentExtractor

                        # Determine file type for extractor
                        ext = Path(filename).suffix.lower().strip('.')
                        if ext == 'doc':
                            ext = 'docx'
                        elif ext == 'xls':
                            ext = 'xlsx'

                        # Extract text from document
                        result = DocumentExtractor.extract(str(file_path), ext)

                        if result.get('error'):
                            current_app.logger.warning(f"Document extraction warning: {result['error']}")
                            return None

                        text_content = result.get('text', '')
                        if text_content.strip():
                            return {
                                'type': 'text_document',
                                'mime_type': 'text/plain',
                                'content': text_content,
                                'filename': filename,
                                'original_mime_type': mime_type
                            }
                        else:
                            current_app.logger.warning(f"No text extracted from {filename}")
                            return None

                    except ImportError:
                        current_app.logger.error("DocumentExtractor not available")
                        return None
                    except Exception as e:
                        current_app.logger.error(f"Error extracting {filename}: {str(e)}")
                        return None

            return None

        except Exception as e:
            current_app.logger.error(f"Error reading attachment: {str(e)}")
            return None

    @staticmethod
    def _get_user_api_key(provider: str, user_id: Optional[int] = None) -> Optional[str]:
        """
        Get API key for a provider, checking user's database keys first, then system admin keys.

        Priority order:
        1. User-specific key from database (if user is authenticated and has one)
        2. System-level admin key from AdminSettings

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai')
            user_id: Optional user ID to fetch user-specific key

        Returns:
            str: API key if found, None otherwise
        """
        # Home Edition: Use system-level API keys only (from AdminSettings)
        from app.models.admin_settings import AdminSettings
        system_key = AdminSettings.get_system_api_key(provider)
        if system_key:
            return system_key

        return None

    @staticmethod
    def get_response(messages: List[Dict[str, Any]], provider: str, model_name: Optional[str] = None,
                    user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Dict[str, Any]:
        """
        Get response from AI provider with support for multimodal inputs (images, documents)

        Args:
            messages: List of chat messages (may include 'attachments' key)
            provider: AI provider name ('gemini', 'openai', 'anthropic', 'xai', 'lmstudio', 'lm_studio', 'ollama')
            model_name: Optional model name override
            user_id: Optional user ID for user-specific API keys
            upload_folder: Base folder for file uploads

        Returns:
            Dict with 'response' or 'error' key
        """
        # Normalize provider name for backward compatibility
        provider = provider.lower()
        if provider == 'lm_studio':
            provider = 'lmstudio'

        if provider == 'gemini':
            return AIService._get_gemini_response(messages, user_id, upload_folder)
        elif provider == 'openai':
            return AIService._get_openai_response(messages, model_name, user_id, upload_folder)
        elif provider == 'anthropic':
            return AIService._get_anthropic_response(messages, model_name, user_id, upload_folder)
        elif provider == 'xai':
            return AIService._get_grok_response(messages, model_name, user_id, upload_folder)
        elif provider == 'lmstudio':
            return AIService._get_lmstudio_response(messages, model_name, user_id, upload_folder)
        elif provider == 'ollama':
            return AIService._get_ollama_response(messages, model_name, user_id, upload_folder)
        else:
            return {"error": f"Unknown provider: {provider}"}

    @staticmethod
    def _get_gemini_response(messages: List[Dict[str, Any]], user_id: Optional[int] = None,
                            upload_folder: str = 'uploads') -> Dict[str, Any]:
        """Call Google Gemini API using Python SDK with vision support"""
        api_key = AIService._get_user_api_key('gemini', user_id)
        if not api_key:
            return {"error": "Gemini API key not configured. Please add your API key in your application settings."}

        # Get model ID from AdminSettings (system-level)
        from app.models.admin_settings import AdminSettings
        model_name = AdminSettings.get_system_model_id('gemini')

        # Extract system messages for Gemini's system_instruction parameter
        # Gemini only accepts "user" and "model" roles, not "system"
        system_instructions = []
        non_system_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                if msg.get('content'):
                    system_instructions.append(msg['content'])
            else:
                non_system_messages.append(msg)

        # Combine all system messages into a single system instruction
        combined_system_instruction = "\n\n".join(system_instructions) if system_instructions else None

        # Convert non-system messages to Gemini format (with multimodal support)
        # Note: PDFs, DOCX, XLSX are extracted as text by _get_attachment_content
        gemini_messages = []
        for msg in non_system_messages:
            role = 'model' if msg['role'] == 'assistant' else 'user'
            parts = []

            # Add text content
            if msg.get('content'):
                parts.append({"text": msg['content']})

            # Add attachments if present
            if msg.get('attachments'):
                for attachment in msg['attachments']:
                    att_content = AIService._get_attachment_content(attachment, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image':
                            # Gemini supports inline images
                            parts.append({
                                "inline_data": {
                                    "mime_type": att_content['mime_type'],
                                    "data": att_content['base64']
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            # Include text documents as text
                            parts.append({
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            gemini_messages.append({
                "role": role,
                "parts": parts
            })

        try:
            # Initialize Gemini client with API key
            client = genai.Client(api_key=api_key)

            # Build config with system instruction if present
            config = None
            if combined_system_instruction:
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=combined_system_instruction
                )

            # Generate response using the SDK
            response = client.models.generate_content(
                model=model_name,
                contents=gemini_messages,
                config=config
            )

            # Return the response text
            return {"response": response.text}

        except Exception as e:
            error_message = str(e)
            # Handle common errors
            if "API_KEY_INVALID" in error_message or "invalid_api_key" in error_message.lower():
                return {"error": "Invalid Gemini API key. Please check your API key in application settings."}
            elif "quota" in error_message.lower():
                return {"error": "Gemini API quota exceeded. Please check your API usage."}
            elif "timeout" in error_message.lower():
                return {"error": "Request to Gemini API timed out"}
            else:
                return {"error": f"Error communicating with Gemini API: {error_message}"}

    @staticmethod
    def _get_gemini_response_stream(messages: List[Dict[str, Any]], user_id: Optional[int] = None,
                                   upload_folder: str = 'uploads') -> Generator[str, None, None]:
        """Stream response from Google Gemini API with vision support"""
        api_key = AIService._get_user_api_key('gemini', user_id)
        if not api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Gemini API key not configured. Please add your API key in your application settings.'})}\n\n"
            return

        # Get model ID from AdminSettings (system-level)
        from app.models.admin_settings import AdminSettings
        model_name = AdminSettings.get_system_model_id('gemini')

        # Extract system messages for Gemini's system_instruction parameter
        # Gemini only accepts "user" and "model" roles, not "system"
        system_instructions = []
        non_system_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                if msg.get('content'):
                    system_instructions.append(msg['content'])
            else:
                non_system_messages.append(msg)

        # Combine all system messages into a single system instruction
        combined_system_instruction = "\n\n".join(system_instructions) if system_instructions else None

        # Convert non-system messages to Gemini format (with multimodal support)
        # Note: PDFs, DOCX, XLSX are extracted as text by _get_attachment_content
        gemini_messages = []
        for msg in non_system_messages:
            role = 'model' if msg['role'] == 'assistant' else 'user'
            parts = []

            # Add text content
            if msg.get('content'):
                parts.append({"text": msg['content']})

            # Add attachments if present
            if msg.get('attachments'):
                for attachment in msg['attachments']:
                    att_content = AIService._get_attachment_content(attachment, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image':
                            parts.append({
                                "inline_data": {
                                    "mime_type": att_content['mime_type'],
                                    "data": att_content['base64']
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            parts.append({
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            gemini_messages.append({
                "role": role,
                "parts": parts
            })

        try:
            # Initialize Gemini client with API key
            client = genai.Client(api_key=api_key)

            full_content = ""
            usage_data = None
            last_chunk = None  # Track the last chunk for usage_metadata

            # Build config with system instruction if present
            config = None
            if combined_system_instruction:
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=combined_system_instruction
                )

            # Generate response using the SDK with streaming
            for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=gemini_messages,
                config=config
            ):
                last_chunk = chunk  # Keep reference to get usage_metadata
                if chunk.text:
                    full_content += chunk.text
                    # Yield SSE-formatted chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk.text})}\n\n"

            # Try to get usage metadata from the last chunk
            if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
                metadata = last_chunk.usage_metadata
                usage_data = {
                    'input_tokens': getattr(metadata, 'prompt_token_count', 0) or 0,
                    'output_tokens': getattr(metadata, 'candidates_token_count', 0) or 0,
                    'total_tokens': getattr(metadata, 'total_token_count', 0) or 0,
                    'estimated': False
                }
            else:
                # Estimate tokens if usage_metadata not available
                from app.services.token_service import TokenService
                output_tokens = TokenService.count_tokens(full_content)
                # Estimate input tokens from message content
                input_text = ' '.join(msg.get('content', '') for msg in messages if isinstance(msg.get('content'), str))
                input_tokens = TokenService.count_tokens(input_text)
                usage_data = {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'estimated': True
                }

            # Send done event with full content and usage data
            done_data = {'type': 'done', 'full_content': full_content}
            if usage_data:
                done_data['usage'] = usage_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except Exception as e:
            error_message = str(e)
            # Handle common errors
            if "API_KEY_INVALID" in error_message or "invalid_api_key" in error_message.lower():
                yield f"data: {json.dumps({'type': 'error', 'content': 'Invalid Gemini API key. Please check your API key in application settings.'})}\n\n"
            elif "quota" in error_message.lower():
                yield f"data: {json.dumps({'type': 'error', 'content': 'Gemini API quota exceeded. Please check your API usage.'})}\n\n"
            elif "timeout" in error_message.lower():
                yield f"data: {json.dumps({'type': 'error', 'content': 'Request to Gemini API timed out'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Error communicating with Gemini API: {error_message}'})}\n\n"

    @staticmethod
    def _get_openai_response(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                            user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Dict[str, Any]:
        """Call OpenAI API with vision support"""
        api_key = AIService._get_user_api_key('openai', user_id)
        if not api_key:
            return {"error": "OpenAI API key not configured. Please add your API key in your application settings."}

        # Get model ID from AdminSettings (system-level)
        if model_name is None:
            from app.models.admin_settings import AdminSettings
            model_name = AdminSettings.get_system_model_id('openai')

        # Convert messages to OpenAI format with multimodal support
        # Note: PDFs, DOCX, XLSX are extracted as text by _get_attachment_content
        openai_messages = []
        has_images = False

        for msg in messages:
            content = []

            # Add text content
            if msg.get('content'):
                content.append({
                    "type": "text",
                    "text": msg['content']
                })

            # Add attachments if present
            if msg.get('attachments'):
                for attachment in msg['attachments']:
                    att_content = AIService._get_attachment_content(attachment, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image':
                            has_images = True
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{att_content['mime_type']};base64,{att_content['base64']}"
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            # Include text documents as text
                            content.append({
                                "type": "text",
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            # Use multimodal format if content is complex, otherwise simple string
            if len(content) == 1 and content[0]['type'] == 'text':
                openai_messages.append({
                    "role": msg['role'],
                    "content": content[0]['text']
                })
            else:
                openai_messages.append({
                    "role": msg['role'],
                    "content": content
                })

        # Check if model supports vision when images are present
        if has_images and not any(x in model_name.lower() for x in ['gpt-4', 'gpt-5', 'vision']):
            return {"error": f"Model '{model_name}' doesn't support image inputs. Please use a vision-capable model."}

        payload = {
            "model": model_name,
            "messages": openai_messages,
            "stream": False
        }

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if ("choices" in data and len(data["choices"]) > 0 and
                "message" in data["choices"][0] and
                "content" in data["choices"][0]["message"]):
                return {"response": data["choices"][0]["message"]["content"]}
            else:
                return {"error": f"Unexpected OpenAI API response format: {data}"}

        except requests.exceptions.HTTPError as http_err:
            error_details = response.json() if response.text else "No additional details."
            return {"error": f"OpenAI API HTTP Error {response.status_code}: {http_err}. Details: {error_details}"}
        except requests.exceptions.ConnectionError as conn_err:
            return {"error": f"Connection Error to OpenAI API: {str(conn_err)}"}
        except requests.exceptions.Timeout:
            return {"error": "Request to OpenAI API timed out"}
        except Exception as e:
            return {"error": f"Error communicating with OpenAI API: {str(e)}"}

    @staticmethod
    def _get_openai_response_stream(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                                    user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Generator[str, None, None]:
        """Stream response from OpenAI API with vision support"""
        api_key = AIService._get_user_api_key('openai', user_id)
        if not api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': 'OpenAI API key not configured. Please add your API key in your application settings.'})}\n\n"
            return

        # Get model ID from AdminSettings (system-level)
        if model_name is None:
            from app.models.admin_settings import AdminSettings
            model_name = AdminSettings.get_system_model_id('openai')

        # Convert messages to OpenAI format with multimodal support
        # Note: PDFs, DOCX, XLSX are extracted as text by _get_attachment_content
        openai_messages = []
        has_images = False

        for msg in messages:
            content = []

            # Add text content
            if msg.get('content'):
                content.append({
                    "type": "text",
                    "text": msg['content']
                })

            # Add attachments if present
            if msg.get('attachments'):
                for attachment in msg['attachments']:
                    att_content = AIService._get_attachment_content(attachment, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image':
                            has_images = True
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{att_content['mime_type']};base64,{att_content['base64']}"
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            content.append({
                                "type": "text",
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            # Use multimodal format if content is complex, otherwise simple string
            if len(content) == 1 and content[0]['type'] == 'text':
                openai_messages.append({
                    "role": msg['role'],
                    "content": content[0]['text']
                })
            else:
                openai_messages.append({
                    "role": msg['role'],
                    "content": content
                })

        # Check if model supports vision when images are present
        if has_images and not any(x in model_name.lower() for x in ['gpt-4', 'gpt-5', 'vision']):
            yield f"data: {json.dumps({'type': 'error', 'content': f'Model {model_name} does not support image inputs. Please use a vision-capable model.'})}\n\n"
            return

        payload = {
            "model": model_name,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True}  # Request token usage with streaming
        }

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=60,
                stream=True
            )
            response.raise_for_status()

            full_content = ""
            usage_data = None  # Will capture token usage from final chunk

            # Stream the response
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]  # Remove 'data: ' prefix

                        if data_str == '[DONE]':
                            break

                        try:
                            chunk_data = json.loads(data_str)

                            # Capture usage data if present (sent in final chunk with stream_options)
                            if 'usage' in chunk_data and chunk_data['usage']:
                                usage_data = {
                                    'input_tokens': chunk_data['usage'].get('prompt_tokens', 0),
                                    'output_tokens': chunk_data['usage'].get('completion_tokens', 0),
                                    'total_tokens': chunk_data['usage'].get('total_tokens', 0),
                                    'estimated': False
                                }

                            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                delta = chunk_data['choices'][0].get('delta', {})
                                content = delta.get('content')
                                if content:  # Only process if content is not None or empty
                                    full_content += content
                                    # Yield SSE-formatted chunk
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue

            # Validate and send done event with full content and usage data
            done_data = {'type': 'done', 'full_content': full_content}

            # Validate token count - if it seems unreasonable, estimate instead
            if usage_data and full_content:
                output_tokens = usage_data.get('output_tokens', 0)
                # Rough validation: output tokens should be roughly chars/4, allow generous margin
                # If API returns more than 2x the character count, it's likely wrong
                max_reasonable = max(len(full_content) * 2, 50)
                if output_tokens > max_reasonable:
                    # API returned unreasonable count, estimate instead
                    from app.services.token_service import TokenService
                    estimated_output = TokenService.count_tokens(full_content)
                    usage_data = {
                        'input_tokens': usage_data.get('input_tokens', 0),
                        'output_tokens': estimated_output,
                        'total_tokens': usage_data.get('input_tokens', 0) + estimated_output,
                        'estimated': True
                    }

            if usage_data:
                done_data['usage'] = usage_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"OpenAI API HTTP Error {response.status_code}: {http_err}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Connection Error to OpenAI API'})}\n\n"
        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Request to OpenAI API timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error communicating with OpenAI API: {str(e)}'})}\n\n"

    @staticmethod
    def _get_anthropic_response(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                               user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Dict[str, Any]:
        """Call Anthropic Claude API with vision and PDF support"""
        api_key = AIService._get_user_api_key('anthropic', user_id)
        if not api_key:
            return {"error": "Anthropic API key not configured. Please add your API key in your application settings."}

        # Get model ID from AdminSettings (system-level)
        if model_name is None:
            from app.models.admin_settings import AdminSettings
            model_name = AdminSettings.get_system_model_id('anthropic')

        # Convert messages to Anthropic format (separate system message if present)
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                content = []

                # Add text content
                if msg.get('content'):
                    content.append({
                        "type": "text",
                        "text": msg['content']
                    })

                # Add attachments if present
                if msg.get('attachments'):
                    for attachment in msg['attachments']:
                        att_content = AIService._get_attachment_content(attachment, upload_folder)
                        if att_content:
                            if att_content['type'] == 'image':
                                # Claude supports images natively
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": att_content['mime_type'],
                                        "data": att_content['base64']
                                    }
                                })
                            elif att_content['type'] == 'pdf':
                                # Claude supports PDFs natively
                                content.append({
                                    "type": "document",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf",
                                        "data": att_content['base64']
                                    }
                                })
                            elif att_content['type'] == 'text_document':
                                # Include text documents as text
                                content.append({
                                    "type": "text",
                                    "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                                })

                # Use multimodal format if content is complex, otherwise simple string
                if len(content) == 1 and content[0]['type'] == 'text':
                    anthropic_messages.append({
                        "role": msg['role'],
                        "content": content[0]['text']
                    })
                else:
                    anthropic_messages.append({
                        "role": msg['role'],
                        "content": content
                    })

        payload = {
            "model": model_name,
            "messages": anthropic_messages,
            "max_tokens": 8192
        }

        if system_message:
            payload["system"] = system_message

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if "content" in data and len(data["content"]) > 0:
                return {"response": data["content"][0]["text"]}
            else:
                return {"error": f"Unexpected Anthropic API response format: {data}"}

        except requests.exceptions.HTTPError as http_err:
            error_details = response.json() if response.text else "No additional details."
            return {"error": f"Anthropic API HTTP Error {response.status_code}: {http_err}. Details: {error_details}"}
        except requests.exceptions.ConnectionError as conn_err:
            return {"error": f"Connection Error to Anthropic API: {str(conn_err)}"}
        except requests.exceptions.Timeout:
            return {"error": "Request to Anthropic API timed out"}
        except Exception as e:
            return {"error": f"Error communicating with Anthropic API: {str(e)}"}

    @staticmethod
    def _get_anthropic_response_stream(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                                      user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Generator[str, None, None]:
        """Stream response from Anthropic Claude API with vision and PDF support"""
        api_key = AIService._get_user_api_key('anthropic', user_id)
        if not api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Anthropic API key not configured. Please add your API key in your application settings.'})}\n\n"
            return

        # Get model ID from AdminSettings (system-level)
        if model_name is None:
            from app.models.admin_settings import AdminSettings
            model_name = AdminSettings.get_system_model_id('anthropic')

        # Convert messages to Anthropic format (separate system message if present)
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                content = []

                # Add text content
                if msg.get('content'):
                    content.append({
                        "type": "text",
                        "text": msg['content']
                    })

                # Add attachments if present
                if msg.get('attachments'):
                    for attachment in msg['attachments']:
                        att_content = AIService._get_attachment_content(attachment, upload_folder)
                        if att_content:
                            if att_content['type'] == 'image':
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": att_content['mime_type'],
                                        "data": att_content['base64']
                                    }
                                })
                            elif att_content['type'] == 'pdf':
                                content.append({
                                    "type": "document",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf",
                                        "data": att_content['base64']
                                    }
                                })
                            elif att_content['type'] == 'text_document':
                                content.append({
                                    "type": "text",
                                    "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                                })

                # Use multimodal format if content is complex, otherwise simple string
                if len(content) == 1 and content[0]['type'] == 'text':
                    anthropic_messages.append({
                        "role": msg['role'],
                        "content": content[0]['text']
                    })
                else:
                    anthropic_messages.append({
                        "role": msg['role'],
                        "content": content
                    })

        payload = {
            "model": model_name,
            "messages": anthropic_messages,
            "max_tokens": 8192,
            "stream": True
        }

        if system_message:
            payload["system"] = system_message

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json'
                },
                timeout=60,
                stream=True
            )
            response.raise_for_status()

            full_content = ""
            usage_data = None  # Will capture token usage from message_delta

            # Stream the response
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]  # Remove 'data: ' prefix

                        try:
                            event_data = json.loads(data_str)
                            event_type = event_data.get('type')

                            # Handle different event types
                            if event_type == 'content_block_delta':
                                delta = event_data.get('delta', {})
                                if delta.get('type') == 'text_delta':
                                    content = delta.get('text', '')
                                    full_content += content
                                    # Yield SSE-formatted chunk
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                            elif event_type == 'message_delta':
                                # Capture usage data from message_delta event (sent at end)
                                usage = event_data.get('usage', {})
                                if usage:
                                    # message_delta contains output_tokens, we need to combine with message_start for input
                                    output_tokens = usage.get('output_tokens', 0)
                                    if usage_data:
                                        usage_data['output_tokens'] = output_tokens
                                        usage_data['total_tokens'] = usage_data['input_tokens'] + output_tokens
                                    else:
                                        usage_data = {
                                            'input_tokens': 0,
                                            'output_tokens': output_tokens,
                                            'total_tokens': output_tokens,
                                            'estimated': False
                                        }

                            elif event_type == 'message_start':
                                # Capture input tokens from message_start event
                                message = event_data.get('message', {})
                                usage = message.get('usage', {})
                                if usage:
                                    input_tokens = usage.get('input_tokens', 0)
                                    usage_data = {
                                        'input_tokens': input_tokens,
                                        'output_tokens': 0,
                                        'total_tokens': input_tokens,
                                        'estimated': False
                                    }

                            elif event_type == 'message_stop':
                                # Message complete
                                break

                        except json.JSONDecodeError:
                            continue

            # Validate token count - if it seems unreasonable, estimate instead
            # Some API responses return inflated token counts
            if usage_data and full_content:
                output_tokens = usage_data.get('output_tokens', 0)
                # If output tokens is more than 2x the character count, it's likely wrong
                # (typical ratio is ~4 chars per token, so 2x chars is very generous)
                max_reasonable = max(len(full_content) * 2, 50)  # At least 50 to avoid false positives on short responses
                if output_tokens > max_reasonable:
                    # Fall back to local estimation
                    from app.services.token_service import TokenService
                    estimated_output = TokenService.count_tokens(full_content)
                    usage_data = {
                        'input_tokens': usage_data.get('input_tokens', 0),
                        'output_tokens': estimated_output,
                        'total_tokens': usage_data.get('input_tokens', 0) + estimated_output,
                        'estimated': True
                    }

            # Send done event with full content and usage data
            done_data = {'type': 'done', 'full_content': full_content}
            if usage_data:
                done_data['usage'] = usage_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"Anthropic API HTTP Error {response.status_code}: {http_err}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Connection Error to Anthropic API'})}\n\n"
        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Request to Anthropic API timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error communicating with Anthropic API: {str(e)}'})}\n\n"

    @staticmethod
    def _get_grok_response(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                          user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Dict[str, Any]:
        """Call xAI Grok API with vision support using HTTP API"""
        api_key = AIService._get_user_api_key('xai', user_id)
        if not api_key:
            return {"error": "xAI API key not configured. Please add your API key in your application settings."}

        # Get model ID from AdminSettings (system-level)
        if model_name is None:
            from app.models.admin_settings import AdminSettings
            model_name = AdminSettings.get_system_model_id('xai')

        # Convert messages to xAI API format (OpenAI-compatible)
        xai_messages = []

        for msg in messages:
            content = []

            # Add text content
            if msg.get('content'):
                content.append({
                    "type": "text",
                    "text": msg['content']
                })

            # Add attachments if present
            if msg.get('attachments'):
                for attachment in msg['attachments']:
                    att_content = AIService._get_attachment_content(attachment, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image':
                            # xAI supports image_url format like OpenAI
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{att_content['mime_type']};base64,{att_content['base64']}"
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            # Include extracted text from documents
                            content.append({
                                "type": "text",
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            # Use multimodal format if content is complex, otherwise simple string
            if len(content) == 1 and content[0]['type'] == 'text':
                xai_messages.append({
                    "role": msg['role'],
                    "content": content[0]['text']
                })
            else:
                xai_messages.append({
                    "role": msg['role'],
                    "content": content
                })

        payload = {
            "model": model_name,
            "messages": xai_messages,
            "stream": False
        }

        try:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=3600  # Long timeout for reasoning models
            )
            response.raise_for_status()
            data = response.json()

            if ("choices" in data and len(data["choices"]) > 0 and
                "message" in data["choices"][0] and
                "content" in data["choices"][0]["message"]):
                response_text = data["choices"][0]["message"]["content"]

                return {"response": response_text}
            else:
                return {"error": f"Unexpected xAI API response format: {data}"}

        except requests.exceptions.HTTPError as http_err:
            error_details = response.json() if response.text else "No additional details."
            return {"error": f"xAI API HTTP Error {response.status_code}: {http_err}. Details: {error_details}"}
        except requests.exceptions.ConnectionError as conn_err:
            return {"error": f"Connection Error to xAI API: {str(conn_err)}"}
        except requests.exceptions.Timeout:
            return {"error": "Request to xAI API timed out"}
        except Exception as e:
            current_app.logger.error(f"xAI API error: {str(e)}")
            return {"error": f"Error communicating with xAI API: {str(e)}"}

    @staticmethod
    def _get_grok_response_stream(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                                 user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Generator[str, None, None]:
        """Stream response from xAI Grok API with vision support using HTTP API"""
        api_key = AIService._get_user_api_key('xai', user_id)
        if not api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': 'xAI API key not configured. Please add your API key in your application settings.'})}\n\n"
            return

        # Get model ID from AdminSettings (system-level)
        if model_name is None:
            from app.models.admin_settings import AdminSettings
            model_name = AdminSettings.get_system_model_id('xai')

        # Convert messages to xAI API format (OpenAI-compatible)
        xai_messages = []

        for msg in messages:
            content = []

            # Add text content
            if msg.get('content'):
                content.append({
                    "type": "text",
                    "text": msg['content']
                })

            # Add attachments if present
            if msg.get('attachments'):
                for attachment in msg['attachments']:
                    att_content = AIService._get_attachment_content(attachment, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image':
                            # xAI supports image_url format like OpenAI
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{att_content['mime_type']};base64,{att_content['base64']}"
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            # Include extracted text from documents
                            content.append({
                                "type": "text",
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            # Use multimodal format if content is complex, otherwise simple string
            if len(content) == 1 and content[0]['type'] == 'text':
                xai_messages.append({
                    "role": msg['role'],
                    "content": content[0]['text']
                })
            else:
                xai_messages.append({
                    "role": msg['role'],
                    "content": content
                })

        payload = {
            "model": model_name,
            "messages": xai_messages,
            "stream": True,
            "stream_options": {"include_usage": True}  # Request token usage with streaming
        }

        try:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=3600,  # Long timeout for reasoning models
                stream=True
            )
            response.raise_for_status()

            full_content = ""
            usage_data = None  # Will capture token usage from final chunk

            # Stream the response (OpenAI-compatible format)
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]  # Remove 'data: ' prefix

                        if data_str == '[DONE]':
                            break

                        try:
                            chunk_data = json.loads(data_str)

                            # Capture usage data if present (sent in final chunk with stream_options)
                            if 'usage' in chunk_data and chunk_data['usage']:
                                usage_data = {
                                    'input_tokens': chunk_data['usage'].get('prompt_tokens', 0),
                                    'output_tokens': chunk_data['usage'].get('completion_tokens', 0),
                                    'total_tokens': chunk_data['usage'].get('total_tokens', 0),
                                    'estimated': False
                                }

                            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                delta = chunk_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    full_content += content
                                    # Yield SSE-formatted chunk
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue

            # Validate token count - if it seems unreasonable, estimate instead
            # Some API responses return inflated token counts
            if usage_data and full_content:
                output_tokens = usage_data.get('output_tokens', 0)
                # If output tokens is more than 2x the character count, it's likely wrong
                # (typical ratio is ~4 chars per token, so 2x chars is very generous)
                max_reasonable = max(len(full_content) * 2, 50)  # At least 50 to avoid false positives on short responses
                if output_tokens > max_reasonable:
                    # Fall back to local estimation
                    from app.services.token_service import TokenService
                    estimated_output = TokenService.count_tokens(full_content)
                    usage_data = {
                        'input_tokens': usage_data.get('input_tokens', 0),
                        'output_tokens': estimated_output,
                        'total_tokens': usage_data.get('input_tokens', 0) + estimated_output,
                        'estimated': True
                    }

            # Send done event with full content and usage data
            done_data = {'type': 'done', 'full_content': full_content}
            if usage_data:
                done_data['usage'] = usage_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"xAI API HTTP Error {response.status_code}: {http_err}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Connection Error to xAI API'})}\n\n"
        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Request to xAI API timed out'})}\n\n"
        except Exception as e:
            current_app.logger.error(f"xAI API streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error communicating with xAI API: {str(e)}'})}\n\n"

    @staticmethod
    def _get_lmstudio_response(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                              user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Dict[str, Any]:
        """Call LM Studio local API with optional vision support"""
        # Get system settings from AdminSettings
        from app.models.admin_settings import AdminSettings
        lm_studio_url = AdminSettings.get_local_model_url('lm_studio')
        lm_studio_model_id = AdminSettings.get_system_model_id('lm_studio')

        if model_name is None:
            model_name = lm_studio_model_id

        # Check if vision is enabled for LM Studio
        from app.models.admin_settings import AdminSettings
        vision_enabled = AdminSettings.is_lm_studio_vision_enabled()

        # Check if messages contain images
        has_images = False
        for msg in messages:
            if msg.get('attachments'):
                for att in msg['attachments']:
                    if att.get('file_type') == 'image':
                        has_images = True
                        break
            if has_images:
                break

        # Block images if vision is not enabled
        if has_images and not vision_enabled:
            return {"error": "Enable vision support in Admin Settings if using a vision-capable model."}

        # Convert messages - with optional vision support (OpenAI-compatible format)
        lmstudio_messages = []
        for msg in messages:
            content = []

            # Add text content
            if msg.get('content'):
                content.append({
                    "type": "text",
                    "text": msg['content']
                })

            # Process attachments
            if msg.get('attachments'):
                for att in msg['attachments']:
                    att_content = AIService._get_attachment_content(att, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image' and vision_enabled:
                            # Add image in OpenAI-compatible format
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{att_content['mime_type']};base64,{att_content['base64']}"
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            # Add document as text
                            content.append({
                                "type": "text",
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            # Use multimodal format if content is complex, otherwise simple string
            if len(content) == 1 and content[0]['type'] == 'text':
                lmstudio_messages.append({
                    "role": msg['role'],
                    "content": content[0]['text']
                })
            elif len(content) > 0:
                lmstudio_messages.append({
                    "role": msg['role'],
                    "content": content
                })
            else:
                lmstudio_messages.append({
                    "role": msg['role'],
                    "content": msg.get('content', '')
                })

        payload = {
            "model": model_name,
            "messages": lmstudio_messages,
            "stream": False
        }

        try:
            response = requests.post(lm_studio_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            if ("choices" in data and len(data["choices"]) > 0 and
                "message" in data["choices"][0] and
                "content" in data["choices"][0]["message"]):
                return {"response": data["choices"][0]["message"]["content"]}
            else:
                return {"error": f"Unexpected LM Studio API response format: {data}"}

        except requests.exceptions.ConnectionError as conn_err:
            return {"error": f"Connection Error to LM Studio: Please ensure LM Studio is running at {lm_studio_url} and the model '{model_name}' is loaded."}
        except requests.exceptions.HTTPError as http_err:
            return {"error": f"LM Studio HTTP Error {response.status_code}: {http_err}. Check LM Studio logs for more details."}
        except requests.exceptions.Timeout:
            return {"error": "Request to LM Studio timed out"}
        except Exception as e:
            return {"error": f"Error communicating with LM Studio: {str(e)}"}

    @staticmethod
    def _get_lmstudio_response_stream(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                                     user_id: Optional[int] = None, upload_folder: str = 'uploads',
                                     vision_enabled: bool = False) -> Generator[str, None, None]:
        """Stream response from LM Studio local API with optional vision support (OpenAI-compatible)"""
        # Get system settings from AdminSettings
        from app.models.admin_settings import AdminSettings
        lm_studio_url = AdminSettings.get_local_model_url('lm_studio')
        lm_studio_model_id = AdminSettings.get_system_model_id('lm_studio')

        if model_name is None:
            model_name = lm_studio_model_id

        # Vision is controlled by user toggle passed as parameter

        # Check if messages contain images
        has_images = False
        for msg in messages:
            if msg.get('attachments'):
                for att in msg['attachments']:
                    if att.get('file_type') == 'image':
                        has_images = True
                        break
            if has_images:
                break

        # Block images if vision is not enabled
        if has_images and not vision_enabled:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Enable vision support using the eye icon button next to attachments if using a vision-capable model.'})}\n\n"
            return

        # Convert messages - with optional vision support (OpenAI-compatible format)
        lmstudio_messages = []
        for msg in messages:
            content = []

            # Add text content
            if msg.get('content'):
                content.append({
                    "type": "text",
                    "text": msg['content']
                })

            # Process attachments
            if msg.get('attachments'):
                for att in msg['attachments']:
                    att_content = AIService._get_attachment_content(att, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image' and vision_enabled:
                            # Add image in OpenAI-compatible format
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{att_content['mime_type']};base64,{att_content['base64']}"
                                }
                            })
                        elif att_content['type'] == 'text_document':
                            # Add document as text
                            content.append({
                                "type": "text",
                                "text": f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"
                            })

            # Use multimodal format if content is complex, otherwise simple string
            if len(content) == 1 and content[0]['type'] == 'text':
                lmstudio_messages.append({
                    "role": msg['role'],
                    "content": content[0]['text']
                })
            elif len(content) > 0:
                lmstudio_messages.append({
                    "role": msg['role'],
                    "content": content
                })
            else:
                lmstudio_messages.append({
                    "role": msg['role'],
                    "content": msg.get('content', '')
                })

        payload = {
            "model": model_name,
            "messages": lmstudio_messages,
            "stream": True
        }

        try:
            response = requests.post(lm_studio_url, json=payload, timeout=120, stream=True)
            response.raise_for_status()

            full_content = ""
            usage_data = None  # May be provided by some LM Studio servers

            # Stream the response (OpenAI-compatible format)
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]

                        if data_str == '[DONE]':
                            break

                        try:
                            chunk_data = json.loads(data_str)

                            # Check if server provides usage data (some do)
                            if 'usage' in chunk_data and chunk_data['usage']:
                                usage_data = {
                                    'input_tokens': chunk_data['usage'].get('prompt_tokens', 0),
                                    'output_tokens': chunk_data['usage'].get('completion_tokens', 0),
                                    'total_tokens': chunk_data['usage'].get('total_tokens', 0),
                                    'estimated': False
                                }

                            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                delta = chunk_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    full_content += content
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue

            # If no usage data from server, estimate tokens
            if not usage_data:
                from app.services.token_service import TokenService
                output_tokens = TokenService.count_tokens(full_content)
                # Estimate input tokens from message content
                input_text = ' '.join(
                    msg.get('content', '') if isinstance(msg.get('content'), str)
                    else ' '.join(p.get('text', '') for p in msg.get('content', []) if isinstance(p, dict) and p.get('type') == 'text')
                    for msg in messages
                )
                input_tokens = TokenService.count_tokens(input_text)
                usage_data = {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'estimated': True
                }

            # Send done event with full content and usage data
            done_data = {'type': 'done', 'full_content': full_content}
            if usage_data:
                done_data['usage'] = usage_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Connection Error to LM Studio: Please ensure LM Studio is running at {lm_studio_url}'})}\n\n"
        except requests.exceptions.HTTPError as http_err:
            yield f"data: {json.dumps({'type': 'error', 'content': f'LM Studio HTTP Error: {http_err}'})}\n\n"
        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Request to LM Studio timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error communicating with LM Studio: {str(e)}'})}\n\n"

    @staticmethod
    def _get_ollama_response(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                            user_id: Optional[int] = None, upload_folder: str = 'uploads') -> Dict[str, Any]:
        """Call Ollama local API with optional vision support"""
        # Get system settings from AdminSettings
        from app.models.admin_settings import AdminSettings
        ollama_url = AdminSettings.get_local_model_url('ollama')
        ollama_model_id = AdminSettings.get_system_model_id('ollama')

        if model_name is None:
            model_name = ollama_model_id

        # Check if vision is enabled for Ollama
        from app.models.admin_settings import AdminSettings
        vision_enabled = AdminSettings.is_ollama_vision_enabled()

        # Check if messages contain images
        has_images = False
        for msg in messages:
            if msg.get('attachments'):
                for att in msg['attachments']:
                    if att.get('file_type') == 'image':
                        has_images = True
                        break
            if has_images:
                break

        # Block images if vision is not enabled
        if has_images and not vision_enabled:
            return {"error": "Enable vision support in Admin Settings if using a vision-capable model."}

        # Convert messages - with optional vision support (Ollama format)
        ollama_messages = []
        for msg in messages:
            text_content = msg.get('content', '')
            images = []  # Ollama uses an 'images' array with base64 strings

            # Process attachments
            if msg.get('attachments'):
                for att in msg['attachments']:
                    att_content = AIService._get_attachment_content(att, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image' and vision_enabled:
                            # Add base64 image to images array (Ollama format)
                            images.append(att_content['base64'])
                        elif att_content['type'] == 'text_document':
                            # Add document as text
                            text_content += f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"

            # Build message with optional images array
            message = {
                "role": msg['role'],
                "content": text_content
            }
            if images:
                message["images"] = images

            ollama_messages.append(message)

        payload = {
            "model": model_name,
            "messages": ollama_messages,
            "stream": False
        }

        try:
            response = requests.post(ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            if "message" in data and "content" in data["message"]:
                return {"response": data["message"]["content"]}
            else:
                return {"error": f"Unexpected Ollama API response format: {data}"}

        except requests.exceptions.ConnectionError as conn_err:
            return {"error": f"Connection Error to Ollama: Please ensure Ollama is running at {ollama_url} and the model '{model_name}' is available."}
        except requests.exceptions.HTTPError as http_err:
            return {"error": f"Ollama HTTP Error {response.status_code}: {http_err}. Check Ollama logs for more details."}
        except requests.exceptions.Timeout:
            return {"error": "Request to Ollama timed out"}
        except Exception as e:
            return {"error": f"Error communicating with Ollama: {str(e)}"}

    @staticmethod
    def _get_ollama_response_stream(messages: List[Dict[str, Any]], model_name: Optional[str] = None,
                                   user_id: Optional[int] = None, upload_folder: str = 'uploads',
                                   vision_enabled: bool = False) -> Generator[str, None, None]:
        """Stream response from Ollama local API with optional vision support"""
        # Get system settings from AdminSettings
        from app.models.admin_settings import AdminSettings
        ollama_url = AdminSettings.get_local_model_url('ollama')
        ollama_model_id = AdminSettings.get_system_model_id('ollama')

        if model_name is None:
            model_name = ollama_model_id

        # Vision is controlled by user toggle passed as parameter

        # Check if messages contain images
        has_images = False
        for msg in messages:
            if msg.get('attachments'):
                for att in msg['attachments']:
                    if att.get('file_type') == 'image':
                        has_images = True
                        break
            if has_images:
                break

        # Block images if vision is not enabled
        if has_images and not vision_enabled:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Enable vision support using the eye icon button next to attachments if using a vision-capable model.'})}\n\n"
            return

        # Convert messages - with optional vision support (Ollama format)
        ollama_messages = []
        for msg in messages:
            text_content = msg.get('content', '')
            images = []  # Ollama uses an 'images' array with base64 strings

            # Process attachments
            if msg.get('attachments'):
                for att in msg['attachments']:
                    att_content = AIService._get_attachment_content(att, upload_folder)
                    if att_content:
                        if att_content['type'] == 'image' and vision_enabled:
                            # Add base64 image to images array (Ollama format)
                            images.append(att_content['base64'])
                        elif att_content['type'] == 'text_document':
                            # Add document as text
                            text_content += f"\n\n[File: {att_content['filename']}]\n{att_content['content']}"

            # Build message with optional images array
            message = {
                "role": msg['role'],
                "content": text_content
            }
            if images:
                message["images"] = images

            ollama_messages.append(message)

        payload = {
            "model": model_name,
            "messages": ollama_messages,
            "stream": True
        }

        try:
            response = requests.post(ollama_url, json=payload, timeout=120, stream=True)
            response.raise_for_status()

            full_content = ""
            usage_data = None  # May be provided by Ollama in final response

            # Stream the response (Ollama format - different from OpenAI)
            for line in response.iter_lines():
                if line:
                    try:
                        chunk_data = json.loads(line.decode('utf-8'))
                        if 'message' in chunk_data and 'content' in chunk_data['message']:
                            content = chunk_data['message']['content']
                            full_content += content
                            yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                        # Check if done - Ollama may provide token counts in final chunk
                        if chunk_data.get('done', False):
                            # Ollama provides eval_count (output) and prompt_eval_count (input) in final response
                            prompt_tokens = chunk_data.get('prompt_eval_count', 0)
                            output_tokens = chunk_data.get('eval_count', 0)
                            if prompt_tokens or output_tokens:
                                usage_data = {
                                    'input_tokens': prompt_tokens,
                                    'output_tokens': output_tokens,
                                    'total_tokens': prompt_tokens + output_tokens,
                                    'estimated': False
                                }
                            break
                    except json.JSONDecodeError:
                        continue

            # If no usage data from Ollama, estimate tokens
            if not usage_data:
                from app.services.token_service import TokenService
                output_tokens = TokenService.count_tokens(full_content)
                # Estimate input tokens from message content
                input_text = ' '.join(msg.get('content', '') for msg in messages if isinstance(msg.get('content'), str))
                input_tokens = TokenService.count_tokens(input_text)
                usage_data = {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'estimated': True
                }

            # Send done event with full content and usage data
            done_data = {'type': 'done', 'full_content': full_content}
            if usage_data:
                done_data['usage'] = usage_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Connection Error to Ollama: Please ensure Ollama is running at {ollama_url}'})}\n\n"
        except requests.exceptions.HTTPError as http_err:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Ollama HTTP Error: {http_err}'})}\n\n"
        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Request to Ollama timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error communicating with Ollama: {str(e)}'})}\n\n"

    @staticmethod
    def get_response_stream(messages: List[Dict[str, Any]], provider: str, model_name: Optional[str] = None,
                           user_id: Optional[int] = None, upload_folder: str = 'uploads',
                           rag_context: Optional[str] = None,
                           age_system_prompt: Optional[str] = None,
                           local_vision_enabled: bool = False) -> Generator[str, None, None]:
        """
        Stream response from AI provider with support for multimodal inputs.

        Yields SSE-formatted chunks as strings.

        Args:
            messages: List of chat messages (may include 'attachments' key)
            provider: AI provider name
            model_name: Optional model name override
            user_id: Optional user ID for user-specific API keys
            upload_folder: Base folder for file uploads
            rag_context: Optional RAG context to inject as system message
            age_system_prompt: Optional age-based safety system prompt for child/teen users
            local_vision_enabled: User's toggle for vision support on local models

        Yields:
            SSE-formatted strings with JSON data
        """
        # Normalize provider name
        provider = provider.lower()
        if provider == 'lm_studio':
            provider = 'lmstudio'

        # Inject age-based system prompt FIRST (safety takes priority)
        # This ensures child safety guardrails are always applied before other context
        if age_system_prompt:
            age_system_message = {
                "role": "system",
                "content": age_system_prompt
            }
            messages = [age_system_message] + messages

        # Inject RAG context as a system message if provided
        if rag_context:
            rag_system_message = {
                "role": "system",
                "content": f"""You have access to the following document context that may be relevant to the user's questions.
            Use this information to provide accurate, informed responses. If the context doesn't contain relevant information,
            you can still answer based on your knowledge, but mention that the provided documents didn't contain specific information about that topic.

            {rag_context}

            Remember to cite the source documents when using information from them."""
            }
            # Insert at the beginning of messages
            messages = [rag_system_message] + messages

        try:
            if provider == 'gemini':
                yield from AIService._get_gemini_response_stream(messages, user_id, upload_folder)
            elif provider == 'openai':
                yield from AIService._get_openai_response_stream(messages, model_name, user_id, upload_folder)
            elif provider == 'anthropic':
                yield from AIService._get_anthropic_response_stream(messages, model_name, user_id, upload_folder)
            elif provider == 'xai':
                yield from AIService._get_grok_response_stream(messages, model_name, user_id, upload_folder)
            elif provider == 'lmstudio':
                yield from AIService._get_lmstudio_response_stream(messages, model_name, user_id, upload_folder, local_vision_enabled)
            elif provider == 'ollama':
                yield from AIService._get_ollama_response_stream(messages, model_name, user_id, upload_folder, local_vision_enabled)
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Unknown provider: {provider}'})}\n\n"
        except Exception as e:
            current_app.logger.error(f"Streaming error for provider {provider}: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    @staticmethod
    def convert_messages_for_provider(messages: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
        """
        Convert message format between different providers

        Args:
            messages: Standard message format (role, content)
            provider: Target provider name

        Returns:
            Messages in provider-specific format
        """
        if provider == 'gemini':
            return [
                {
                    "role": 'model' if msg['role'] == 'assistant' else msg['role'],
                    "parts": [{"text": msg['content']}]
                }
                for msg in messages
            ]
        else:
            # OpenAI, Anthropic, LM Studio, Ollama use same format
            return messages
