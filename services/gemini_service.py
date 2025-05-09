# services/gemini_service.py
import streamlit as st
import google.generativeai as genai
import json
from utils.logger import app_logger
from utils.file_utils import save_file, delete_file_from_workspace # Renamed for clarity
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
        if not GOOGLE_API_KEY:
            err_msg = "🔴 Google API Key not configured. Please set `GOOGLE_API_KEY` in `.env` or Streamlit secrets."
            st.error(err_msg) # User-facing error
            app_logger.critical(err_msg)
            # st.stop() # This would halt the app; consider if this is desired behavior here or in app.py
            return None # Allow app to continue but AI features will fail

        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            _gemini_model_client = genai.GenerativeModel(
                model_name=GEMINI_MODEL_NAME,
                generation_config=GEMINI_GENERATION_CONFIG,
                safety_settings=GEMINI_SAFETY_SETTINGS
            )
            app_logger.info(f"Gemini client initialized successfully with model: {GEMINI_MODEL_NAME}")
        except Exception as e:
            err_msg = f"🔴 Failed to initialize Google AI client: {e}"
            st.error(err_msg)
            app_logger.critical(err_msg, exc_info=True)
            _gemini_model_client = None # Ensure it's None on failure
    return _gemini_model_client

def _clean_ai_response_text(ai_response_text: str) -> str:
    """
    Removes potential markdown code fences (e.g., ```json ... ```) from AI response.
    """
    text = ai_response_text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"): # Generic ``` block
        text = text[3:-3].strip()
    return text

def _prepare_gemini_history(chat_history: list, system_prompt: str) -> list:
    """
    Formats chat history for the Gemini API call, including the system prompt.
    Ensures the conversation starts with a user role for the system prompt,
    followed by a model role for the initial "Understood" message.
    """
    gemini_history = []
    # Start with the system prompt as the first user message
    gemini_history.append({"role": "user", "parts": [{"text": system_prompt}]})
    # Gemini API expects alternating user/model roles. Add a model part to prime.
    gemini_history.append({"role": "model", "parts": [{"text": json.dumps([{"action": "chat", "content": "Understood. I will respond only with JSON commands as instructed."}])}]})

    for msg in chat_history:
        role = msg["role"]  # "user" or "assistant"
        content = msg["content"]
        api_role = "model" if role == "assistant" else "user"

        if role == "assistant" and isinstance(content, list): # AI commands list
            try:
                content_str = json.dumps(content)
            except TypeError as e:
                app_logger.error(f"Error serializing assistant message to JSON: {content}. Error: {e}")
                content_str = str(content) # Fallback
        else: # User message or AI chat string
            content_str = str(content)

        if content_str: # Avoid sending empty messages
            gemini_history.append({"role": api_role, "parts": [{"text": content_str}]})
    return gemini_history

def ask_gemini_ai(chat_history: list, current_workspace_files: list[str]) -> str:
    """
    Sends the conversation history to the Gemini AI and returns its raw text response.

    Args:
        chat_history (list): The current list of chat messages from st.session_state.messages.
        current_workspace_files (list[str]): List of Python filenames in the workspace.

    Returns:
        str: The AI's raw text response, expected to be a JSON string of commands,
             or a JSON string representing a chat error message if API call fails.
    """
    model = _initialize_gemini_client()
    if not model:
        app_logger.error("Gemini client not available for ask_gemini_ai.")
        return json.dumps([{"action": "chat", "content": "AI Error: Gemini client is not initialized. Please check API key and configuration."}])

    file_list_str = ', '.join(current_workspace_files) if current_workspace_files else 'None'
    # Dynamically insert the current file list into the system prompt template
    try:
        # Ensure file_list_str is properly escaped if it could contain problematic characters for .format
        # For simple comma-separated filenames, it should be fine.
        system_prompt_with_context = GEMINI_SYSTEM_PROMPT_TEMPLATE.format(file_list=file_list_str)
    except KeyError as e:
        app_logger.error(f"KeyError formatting system prompt: {e}. Placeholder 'file_list' might be missing or misspelled in template.")
        return json.dumps([{"action": "chat", "content": "AI Error: System prompt configuration issue."}])


    gemini_api_history = _prepare_gemini_history(chat_history, system_prompt_with_context)
    app_logger.debug(f"Sending history to Gemini: {json.dumps(gemini_api_history, indent=2)}")

    try:
        response = model.generate_content(gemini_api_history)
        app_logger.debug(f"Received response from Gemini: {response.text}")
        return response.text
    except Exception as e:
        error_message = f"Gemini API call failed: {type(e).__name__} - {str(e)[:150]}"
        app_logger.error(error_message, exc_info=True)

        # More specific error handling based on common issues
        error_content = f"AI Error: {str(e)[:150]}..."
        if "API key not valid" in str(e).lower() or "permission_denied" in str(e).lower():
            error_content = "AI Error: Invalid or missing Google API Key. Please check your configuration."
        elif "429" in str(e) or "quota" in str(e).lower() or "resource has been exhausted" in str(e).lower():
            error_content = "AI Error: API Quota or Rate Limit Exceeded. Please try again later or check your Google Cloud project quotas."
        elif "safety settings" in str(e).lower() or (hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason):
            block_reason = getattr(response.prompt_feedback, 'block_reason', 'unknown') if hasattr(response, 'prompt_feedback') else 'unknown'
            error_content = f"AI Error: Request blocked by safety filters (Reason: {block_reason}). Please revise your prompt."
        elif hasattr(response, 'candidates') and response.candidates and response.candidates[0].finish_reason != 'STOP':
            finish_reason = response.candidates[0].finish_reason
            error_content = f"AI Error: Response generation stopped prematurely (Reason: {finish_reason}). This might be due to safety filters or length limits."

        return json.dumps([{"action": "chat", "content": error_content}])


def parse_and_execute_ai_commands(ai_response_text: str) -> list[dict]:
    """
    Parses the AI's JSON response and performs the requested file actions.
    Updates st.session_state directly for editor content if the active file is modified.

    Args:
        ai_response_text (str): The raw JSON string response from the AI.

    Returns:
        list[dict]: A list of command dictionaries that were processed (or attempted).
                    This is used for displaying AI actions in the chat history.
    """
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

            # Log the command being processed for traceability
            app_logger.info(f"Processing AI command: {command_data}")
            executed_commands_list.append(command_data.copy()) # Add a copy to the list for display

            action = command_data.get("action")
            filename = command_data.get("filename")
            content = command_data.get("content") # For create_update

            if action == "create_update":
                if filename and content is not None:
                    if not filename.endswith(".py"):
                        st.error(f"AI command failed: Filename '{filename}' must end with '.py'.")
                        app_logger.error(f"AI 'create_update' for invalid filename: {filename}")
                        executed_commands_list[-1]['status'] = 'failed: invalid filename' # Add status to displayed command
                        continue

                    success = save_file(filename, content, WORKSPACE_DIR)
                    if success:
                        st.toast(f"AI created/updated: {filename}", icon="💾")
                        app_logger.info(f"AI 'create_update' successful for '{filename}'.")
                        # If this file is currently open in the editor, update editor's content
                        if st.session_state.selected_file == filename:
                            st.session_state.file_content_on_load = content
                            st.session_state.editor_unsaved_content = content
                            st.session_state.last_saved_content = content
                            app_logger.debug(f"Updated session state for active editor file '{filename}' after AI save.")
                        executed_commands_list[-1]['status'] = 'success'
                    else:
                        # save_file already shows st.error and logs
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
                        # If the deleted file was selected in editor, clear editor
                        if st.session_state.selected_file == filename:
                            st.session_state.selected_file = None
                            st.session_state.file_content_on_load = ""
                            st.session_state.editor_unsaved_content = ""
                            st.session_state.last_saved_content = ""
                            app_logger.debug(f"Cleared session state for active editor file '{filename}' after AI delete.")
                        # If deleted file was being previewed, stop preview (handled in app.py based on file list change)
                        executed_commands_list[-1]['status'] = 'success'
                    else:
                        # delete_file_from_workspace already shows st.error and logs
                        app_logger.error(f"AI 'delete' failed for '{filename}'.")
                        executed_commands_list[-1]['status'] = 'failed: delete error'
                else:
                    warn_msg = "AI 'delete' command missing filename."
                    st.warning(warn_msg)
                    app_logger.warning(warn_msg)
                    executed_commands_list[-1]['status'] = 'failed: missing filename'

            elif action == "chat":
                # No file system action, message will be displayed by app.py
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

if __name__ == "__main__":
    # Example usage for testing (requires Streamlit context for st.session_state and st.toast/error)
    app_logger.info("Gemini service module loaded.")
    # To test, you would typically call these functions from app.py or a test script
    # that mocks Streamlit's session state and UI components.

    # Example of how ask_gemini_ai might be called (requires API key and setup)
    # if GOOGLE_API_KEY:
    #     test_history = [{"role": "user", "content": "Create a file called test.py with print('hello')"}]
    #     test_files = []
    #     response = ask_gemini_ai(test_history, test_files)
    #     app_logger.info(f"Test AI response: {response}")
    #     if response:
    #         commands = parse_and_execute_ai_commands(response)
    #         app_logger.info(f"Test executed commands: {commands}")
    # else:
    #     app_logger.warning("Cannot run ask_gemini_ai test without GOOGLE_API_KEY.")
