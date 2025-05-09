# services/gemini_service.py
import streamlit as st
import google.generativeai as genai
import json
from utils.logger import app_logger
from utils.file_utils import save_file, delete_file_from_workspace
from config.settings import (
    GOOGLE_API_KEY, GEMINI_MODEL_NAME, WORKSPACE_DIR,
    GEMINI_SYSTEM_PROMPT_TEMPLATE, GEMINI_GENERATION_CONFIG, GEMINI_SAFETY_SETTINGS
)

# --- Module-level AI Model Client ---
_gemini_model_client = None

def _initialize_gemini_client():
    """
    Initializes and returns the Gemini AI model client.
    Uses a module-level global to avoid re-initialization on every call.
    """
    global _gemini_model_client
    if _gemini_model_client is None:
        app_logger.info("Attempting to initialize Gemini client...")
        if not GOOGLE_API_KEY:
            err_msg = "🔴 Google API Key not configured (GOOGLE_API_KEY is missing or empty in config). Please set `GOOGLE_API_KEY` in `.env` or Streamlit secrets."
            # This error is now primarily shown in app.py's sidebar status.
            # st.error(err_msg) # Avoid direct st.error here if possible, let app.py handle UI
            app_logger.critical(err_msg)
            return None

        app_logger.info(f"Found GOOGLE_API_KEY (length: {len(GOOGLE_API_KEY)}). Proceeding with Gemini client configuration.")

        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            app_logger.info(f"genai.configure called successfully.")
            _gemini_model_client = genai.GenerativeModel(
                model_name=GEMINI_MODEL_NAME,
                generation_config=GEMINI_GENERATION_CONFIG,
                safety_settings=GEMINI_SAFETY_SETTINGS
            )
            app_logger.info(f"Gemini client initialized successfully with model: {GEMINI_MODEL_NAME}")
        except Exception as e:
            # This error is critical and should be visible.
            err_msg_ui = f"🔴 Failed to initialize Google AI client: {type(e).__name__} - {str(e)[:100]}..."
            st.error(err_msg_ui) # Show error in UI as this is a startup/config issue
            app_logger.critical(f"Failed to initialize Google AI client during genai.configure or GenerativeModel instantiation: {e}", exc_info=True)
            _gemini_model_client = None
    return _gemini_model_client

def _clean_ai_response_text(ai_response_text: str) -> str:
    """
    Removes potential markdown code fences (e.g., ```json ... ```) from AI response.
    """
    text = ai_response_text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    return text

def _prepare_gemini_history(chat_history: list, system_prompt: str) -> list:
    """
    Formats chat history for the Gemini API call, including the system prompt.
    """
    gemini_history = []
    gemini_history.append({"role": "user", "parts": [{"text": system_prompt}]})
    gemini_history.append({"role": "model", "parts": [{"text": json.dumps([{"action": "chat", "content": "Understood. I will respond only with JSON commands as instructed."}])}]})

    for msg in chat_history:
        role = msg["role"]
        content = msg["content"]
        api_role = "model" if role == "assistant" else "user"

        if role == "assistant" and isinstance(content, list):
            try:
                content_str = json.dumps(content)
            except TypeError as e:
                app_logger.error(f"Error serializing assistant message to JSON: {content}. Error: {e}")
                content_str = str(content)
        else:
            content_str = str(content)

        if content_str:
            gemini_history.append({"role": api_role, "parts": [{"text": content_str}]})
    return gemini_history

def ask_gemini_ai(chat_history: list, current_workspace_files: list[str]) -> str:
    """
    Sends the conversation history to the Gemini AI and returns its raw text response.
    """
    model = _initialize_gemini_client()
    if not model:
        app_logger.error("Gemini client not available for ask_gemini_ai call because _initialize_gemini_client failed.")
        return json.dumps([{"action": "chat", "content": "AI Error: Gemini client is not initialized. Please check API key and configuration (see logs for details)."}])

    file_list_str = ', '.join(current_workspace_files) if current_workspace_files else 'None'
    
    # --- BEGIN DEBUG LOGGING for system prompt formatting ---
    app_logger.debug(f"GEMINI_SYSTEM_PROMPT_TEMPLATE (first 300 chars): {GEMINI_SYSTEM_PROMPT_TEMPLATE[:300]}")
    if "{file_list}" in GEMINI_SYSTEM_PROMPT_TEMPLATE:
        app_logger.debug("Placeholder '{file_list}' was FOUND in GEMINI_SYSTEM_PROMPT_TEMPLATE string literal.")
    else:
        app_logger.error("Placeholder '{file_list}' was NOT FOUND in GEMINI_SYSTEM_PROMPT_TEMPLATE string literal. This will cause a KeyError if not intended.")
    # --- END DEBUG LOGGING ---

    try:
        system_prompt_with_context = GEMINI_SYSTEM_PROMPT_TEMPLATE.format(file_list=file_list_str)
    except KeyError as e:
        # Log the specific key that caused the error
        app_logger.error(f"KeyError formatting system prompt. Offending key: '{e}'. This means the placeholder '{{{e}}}' was found in the template but not provided as a keyword argument to .format(), OR '{e}' was expected but the placeholder was different (e.g. 'file_list' was expected but the placeholder was misspelled).", exc_info=True)
        return json.dumps([{"action": "chat", "content": f"AI Error: System prompt configuration issue. Offending placeholder key: '{e}'. Please check server logs."}])
    except Exception as e_format: # Catch any other formatting errors
        app_logger.error(f"Unexpected error during system prompt formatting: {e_format}", exc_info=True)
        return json.dumps([{"action": "chat", "content": "AI Error: Critical issue during system prompt formatting. Please check server logs."}])


    gemini_api_history = _prepare_gemini_history(chat_history, system_prompt_with_context)
    app_logger.debug(f"Sending history to Gemini (length: {len(gemini_api_history)} entries). Last user message: {chat_history[-1]['content'] if chat_history and chat_history[-1]['role']=='user' else 'N/A'}")

    try:
        response = model.generate_content(gemini_api_history)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            app_logger.warning(f"Gemini response was blocked. Reason: {response.prompt_feedback.block_reason}. Safety ratings: {response.prompt_feedback.safety_ratings}")
        app_logger.debug(f"Received response from Gemini. Text length: {len(response.text) if response.text else 0}.")
        return response.text
    except Exception as e:
        error_message = f"Gemini API call to model.generate_content failed: {type(e).__name__} - {str(e)[:250]}"
        app_logger.error(error_message, exc_info=True)

        error_content = f"AI Error: API call failed. Details: {str(e)[:150]}..."
        # ... (rest of specific error handling for API call) ...
        if "API key not valid" in str(e).lower() or "permission_denied" in str(e).lower() or "PERMISSION_DENIED" in str(e).upper():
            error_content = "AI Error: Invalid or missing Google API Key, or key lacks permissions for the model. Please verify your key and its configuration in Google AI Studio / Google Cloud."
        elif "429" in str(e) or "quota" in str(e).lower() or "resource has been exhausted" in str(e).lower():
            error_content = "AI Error: API Quota or Rate Limit Exceeded. Please try again later or check your Google Cloud project quotas."
        # ... (other specific error messages)
        
        return json.dumps([{"action": "chat", "content": error_content}])


def parse_and_execute_ai_commands(ai_response_text: str) -> list[dict]:
    # ... (rest of the function remains the same) ...
    cleaned_text = _clean_ai_response_text(ai_response_text)
    executed_commands_list = []

    try:
        commands = json.loads(cleaned_text)
        if not isinstance(commands, list):
            err_msg = f"AI response was valid JSON, but not a list of commands. Received: {cleaned_text}"
            st.error(err_msg)
            app_logger.error(err_msg)
            return [{"action": "chat", "content": "AI Error: Response was not a list of commands."}]

        for command_data in commands:
            if not isinstance(command_data, dict):
                warn_msg = f"AI sent an invalid command format (not a dict): {command_data}"
                st.warning(warn_msg)
                app_logger.warning(warn_msg)
                executed_commands_list.append({"action": "chat", "content": f"AI Warning: Invalid command format: {command_data}"})
                continue

            app_logger.info(f"Processing AI command: {command_data}")
            executed_commands_list.append(command_data.copy())

            action = command_data.get("action")
            filename = command_data.get("filename")
            content = command_data.get("content")

            if action == "create_update":
                if filename and content is not None:
                    if not filename.endswith(".py"):
                        st.error(f"AI command failed: Filename '{filename}' must end with '.py'.")
                        app_logger.error(f"AI 'create_update' for invalid filename: {filename}")
                        executed_commands_list[-1]['status'] = 'failed: invalid filename'
                        continue

                    success = save_file(filename, content, WORKSPACE_DIR)
                    if success:
                        st.toast(f"AI created/updated: {filename}", icon="💾")
                        app_logger.info(f"AI 'create_update' successful for '{filename}'.")
                        if st.session_state.selected_file == filename:
                            st.session_state.file_content_on_load = content
                            st.session_state.editor_unsaved_content = content
                            st.session_state.last_saved_content = content
                            app_logger.debug(f"Updated session state for active editor file '{filename}' after AI save.")
                        executed_commands_list[-1]['status'] = 'success'
                    else:
                        app_logger.error(f"AI 'create_update' failed for '{filename}'.")
                        executed_commands_list[-1]['status'] = 'failed: save error'
                else:
                    warn_msg = "AI 'create_update' command missing filename or content."
                    st.warning(warn_msg)
                    app_logger.warning(warn_msg)
                    executed_commands_list[-1]['status'] = 'failed: missing parameters'


            elif action == "delete":
                if filename:
                    success = delete_file_from_workspace(filename, WORKSPACE_DIR)
                    if success:
                        app_logger.info(f"AI 'delete' successful for '{filename}'.")
                        if st.session_state.selected_file == filename:
                            st.session_state.selected_file = None
                            st.session_state.file_content_on_load = ""
                            st.session_state.editor_unsaved_content = ""
                            st.session_state.last_saved_content = ""
                            app_logger.debug(f"Cleared session state for active editor file '{filename}' after AI delete.")
                        executed_commands_list[-1]['status'] = 'success'
                    else:
                        app_logger.error(f"AI 'delete' failed for '{filename}'.")
                        executed_commands_list[-1]['status'] = 'failed: delete error'
                else:
                    warn_msg = "AI 'delete' command missing filename."
                    st.warning(warn_msg)
                    app_logger.warning(warn_msg)
                    executed_commands_list[-1]['status'] = 'failed: missing filename'

            elif action == "chat":
                app_logger.info(f"AI 'chat' action: {command_data.get('content')}")
                executed_commands_list[-1]['status'] = 'chat message'
                pass

            else:
                warn_msg = f"AI sent unknown action: '{action}'."
                st.warning(warn_msg)
                app_logger.warning(warn_msg)
                executed_commands_list[-1]['status'] = f'failed: unknown action ({action})'

        return executed_commands_list

    except json.JSONDecodeError:
        err_msg = f"AI response was not valid JSON. Raw response:\n```\n{cleaned_text}\n```"
        st.error(err_msg)
        app_logger.error(err_msg)
        return [{"action": "chat", "content": f"AI Error: Invalid JSON received. Response: {ai_response_text}"}]
    except Exception as e:
        err_msg = f"Unexpected error processing AI commands: {e}"
        st.error(err_msg)
        app_logger.error(err_msg, exc_info=True)
        return [{"action": "chat", "content": f"Critical Error: Could not process AI commands due to: {e}"}]
