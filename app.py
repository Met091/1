# app.py
import streamlit as st
from streamlit_option_menu import option_menu
from streamlit_ace import st_ace
import streamlit_antd_components as sac # For specific buttons like Save/Delete group
import time
from pathlib import Path

# --- Project-specific Imports ---
from config.settings import (
    ACE_DEFAULT_THEME, ACE_DEFAULT_KEYBINDING, ACE_FONT_SIZE, ACE_TAB_SIZE, ACE_WRAP_LINES,
    GEMINI_MODEL_NAME, GEMINI_SYSTEM_PROMPT_TEMPLATE, WORKSPACE_DIR
)
from utils.session_manager import initialize_session_state
from utils.file_utils import (
    get_workspace_python_files, read_file, save_file, delete_file_from_workspace
)
from services.gemini_service import (
    ask_gemini_ai, parse_and_execute_ai_commands
)
from services.preview_service import start_preview, stop_preview
from utils.logger import app_logger

# --- Page Configuration (Must be the first Streamlit command) ---
st.set_page_config(
    layout="wide",
    page_title="AI App Generator Pro",
    page_icon="🤖" # Optional: Add a page icon
)

# --- Load Custom CSS ---
def load_css(file_path: str = "style.css"):
    """Loads custom CSS from a file into the Streamlit app."""
    try:
        with open(file_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        app_logger.info(f"Custom CSS '{file_path}' loaded successfully.")
    except FileNotFoundError:
        app_logger.warning(f"CSS file '{file_path}' not found. Using default styles.")
    except Exception as e:
        app_logger.error(f"Error loading CSS '{file_path}': {e}", exc_info=True)

load_css() # Load custom styles defined in style.css

# --- Initialize Session State (Early in the script) ---
initialize_session_state()
# Note: Gemini client is initialized lazily by gemini_service when first needed.

# --- Main Application UI ---
st.title("🤖 AI Streamlit App Generator (Pro Edition)")
st.markdown("---")


# --- Sidebar ---
with st.sidebar:
    st.header("💬 Chat & Controls")
    st.markdown("---")

    # --- Chat History Display ---
    # Use a container with a fixed height for scrollable chat history
    chat_container_height = st.session_state.get("chat_container_height", 400) # Default height
    chat_container = st.container(height=chat_container_height)

    with chat_container:
        if not st.session_state.messages:
            st.info("Chat history is empty. Type your instructions below to get started with the AI.")
        else:
            for message_idx, message in enumerate(st.session_state.messages):
                role = message["role"]
                content = message["content"]
                avatar = "🧑‍💻" if role == "user" else "🤖"

                with st.chat_message(role, avatar=avatar):
                    if role == "assistant" and isinstance(content, list): # AI commands
                        # Format AI's command list for display
                        file_actions_summary = ""
                        chat_responses = []
                        code_snippets = []

                        for command in content:
                            if not isinstance(command, dict): continue

                            action = command.get("action")
                            filename = command.get("filename")
                            cmd_content = command.get("content") # Content for create_update or chat
                            status = command.get("status", "processed") # Get status if available

                            icon = "📝"
                            if status == 'success': icon = "✅"
                            elif 'failed' in status: icon = "❌"
                            elif status == 'chat message': icon = "💬"


                            if action == "create_update":
                                file_actions_summary += f"{icon} **{status.capitalize()}:** `{filename}` (Created/Updated)\n"
                                if cmd_content and status == 'success': # Show snippet only on success
                                    code_snippets.append({"filename": filename, "content": cmd_content})
                            elif action == "delete":
                                file_actions_summary += f"{icon} **{status.capitalize()}:** `{filename}` (Deleted)\n"
                            elif action == "chat":
                                chat_responses.append(str(cmd_content or "..."))
                            else: # Unknown action
                                file_actions_summary += f"⚠️ **Unknown Action:** `{action}` for `{filename}`\n"

                        full_display_text = (file_actions_summary + "\n".join(chat_responses)).strip()
                        if full_display_text:
                            st.markdown(full_display_text)
                        elif not code_snippets: # If no text and no snippets
                             st.markdown("(AI performed an action without textual output)")

                        for i, snippet in enumerate(code_snippets):
                            with st.expander(f"View AI-generated code for `{snippet['filename']}`", expanded=False):
                                st.code(snippet['content'], language="python", key=f"ai_code_{message_idx}_{i}")

                    elif isinstance(content, str): # User message or simple AI chat
                        st.markdown(content)
                    else: # Fallback for unexpected content type
                        st.warning(f"Unexpected message format: {type(content)}")
                        app_logger.warning(f"Unexpected message format in chat: {content}")

    # --- Chat Input Box ---
    user_prompt = st.chat_input("Tell the AI what to do (e.g., 'Create hello.py with a title')")

    if user_prompt:
        st.session_state.ai_is_thinking = True # Set thinking flag
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        app_logger.info(f"User prompt: {user_prompt}")
        st.rerun() # Rerun to show user message and spinner immediately

    if st.session_state.ai_is_thinking and st.session_state.messages[-1]["role"] == "user":
        with st.spinner("🧠 AI is thinking... Please wait."):
            current_files = get_workspace_python_files(WORKSPACE_DIR)
            app_logger.debug(f"Files for AI context: {current_files}")

            # Send the *entire* chat history (including the latest user prompt) to the AI
            ai_response_text = ask_gemini_ai(st.session_state.messages, current_files)
            app_logger.debug(f"Raw AI response: {ai_response_text}")

            # Parse the AI's response and execute file commands
            # This function now handles session state updates for editor if active file changes
            ai_commands_executed = parse_and_execute_ai_commands(ai_response_text)
            app_logger.info(f"AI commands executed: {ai_commands_executed}")

        st.session_state.messages.append({"role": "assistant", "content": ai_commands_executed})
        st.session_state.ai_is_thinking = False # Reset thinking flag
        st.rerun() # Rerun to show AI response and update UI (file list, editor)

    st.markdown("---")
    # --- Status Info ---
    st.subheader("Status & Info")
    st.caption(f"Using AI model: `{GEMINI_MODEL_NAME}`")
    st.caption(f"Workspace: `{WORKSPACE_DIR.resolve()}`")
    if GOOGLE_API_KEY:
        st.success("Google API Key loaded.", icon="✅")
    else:
        st.error("Google API Key not found. AI features will not work.", icon="❗")
    st.warning(
        "**Note:** Always review AI-generated code before running previews. "
        "The `create_update` command overwrites files without confirmation.",
        icon="⚠️"
    )

# --- Main Area Tabs ---
selected_tab = option_menu(
    menu_title=None, # Required but can be None
    options=["Workspace & Editor", "Live Preview"],
    icons=["folder-open", "play-circle-fill"], # Updated icons
    orientation="horizontal",
    key="main_tab_menu",
    styles={ # Optional: Custom styling for tabs
        "container": {"padding": "5px !important", "background-color": "var(--secondary-background-color)"},
        "icon": {"font-size": "18px"},
        "nav-link": {"font-size": "16px", "text-align": "center", "margin":"0px 5px", "--hover-color": "#eee"},
        "nav-link-selected": {"background-color": "var(--primary-color)", "color": "white"},
    }
)
st.markdown("---")

# --- Workspace Tab ---
if selected_tab == "Workspace & Editor":
    st.header("📂 Workspace & Code Editor")

    file_list_col, editor_col = st.columns([0.35, 0.65]) # Adjust column ratio as needed

    with file_list_col:
        st.subheader("Project Files")
        python_files = get_workspace_python_files(WORKSPACE_DIR)

        if not python_files and not st.session_state.selected_file:
            st.info("Workspace is empty. Use the chat to ask the AI to create a new Python file.")

        # Dropdown for file selection
        # Add a "None" or "Select a file" option if desired, or default to first file
        select_options = ["--- Select a file ---"] + python_files
        current_selection_idx = 0
        if st.session_state.selected_file and st.session_state.selected_file in select_options:
            current_selection_idx = select_options.index(st.session_state.selected_file)

        selected_option = st.selectbox(
            "Edit file:",
            options=select_options,
            index=current_selection_idx,
            key="file_selector_dropdown",
            label_visibility="collapsed"
        )

        # Handle file selection change
        newly_selected_filename = selected_option if selected_option != "--- Select a file ---" else None
        if newly_selected_filename != st.session_state.selected_file:
            st.session_state.selected_file = newly_selected_filename
            app_logger.info(f"User selected file: {newly_selected_filename}")
            if newly_selected_filename:
                file_content = read_file(newly_selected_filename, WORKSPACE_DIR)
                if file_content is None: # File might have been deleted externally or read error
                    file_content = f"# ERROR: Could not read file '{newly_selected_filename}'. It might have been deleted."
                    st.error(f"Could not load '{newly_selected_filename}'.")
                st.session_state.file_content_on_load = file_content
                st.session_state.editor_unsaved_content = file_content
                st.session_state.last_saved_content = file_content
            else: # "--- Select a file ---" chosen
                st.session_state.file_content_on_load = ""
                st.session_state.editor_unsaved_content = ""
                st.session_state.last_saved_content = ""
            st.rerun() # Rerun to load new file into editor

    with editor_col:
        st.subheader("Code Editor")
        selected_filename_for_editor = st.session_state.selected_file

        if selected_filename_for_editor:
            st.caption(f"Currently editing: `{selected_filename_for_editor}`")

            editor_current_text = st_ace(
                value=st.session_state.get('editor_unsaved_content', ''), # Show unsaved content
                language="python",
                theme=ACE_DEFAULT_THEME,
                keybinding=ACE_DEFAULT_KEYBINDING,
                font_size=ACE_FONT_SIZE,
                tab_size=ACE_TAB_SIZE,
                wrap=ACE_WRAP_LINES,
                auto_update=False, # Manual update via session state to control reruns
                height=500, # Set a fixed height for the editor
                key=f"ace_editor_{selected_filename_for_editor}" # Unique key for editor state
            )

            # Update session state if editor text changes (user typing)
            if editor_current_text != st.session_state.editor_unsaved_content:
                st.session_state.editor_unsaved_content = editor_current_text
                # No rerun here to allow smooth typing; rerun on button actions or explicit triggers
                # However, to update "unsaved changes" status, a rerun is needed.
                # This can be a bit jumpy. Consider debouncing or a dedicated "check changes" button.
                # For now, let's rerun to update the save button state.
                st.rerun()


            has_unsaved_changes = (editor_current_text != st.session_state.last_saved_content)
            if has_unsaved_changes:
                st.warning("You have unsaved changes.", icon="⚠️")

            # --- Editor Action Buttons (Save, Delete) ---
            # Using streamlit-antd-components for grouped buttons with icons
            editor_buttons_items = [
                sac.ButtonsItem(label="Save Changes", icon="save", disabled=not has_unsaved_changes),
                sac.ButtonsItem(label="Delete File", icon="delete", color="red"), # Antd 'delete' icon
            ]
            clicked_editor_button_label = sac.buttons(
                items=editor_buttons_items, index=None, format_func='title',
                align='end', size='small', return_index=False, # Return label
                key="editor_action_buttons"
            )

            if clicked_editor_button_label == "Save Changes":
                if save_file(selected_filename_for_editor, editor_current_text, WORKSPACE_DIR):
                    st.session_state.file_content_on_load = editor_current_text # Update baseline
                    st.session_state.last_saved_content = editor_current_text   # Mark as saved
                    st.toast(f"Saved: `{selected_filename_for_editor}`", icon="💾")
                    app_logger.info(f"User saved file: {selected_filename_for_editor}")
                    time.sleep(0.5) # Let toast show
                    st.rerun() # Rerun to update button state (disable save)
                # else: save_file already shows st.error and logs

            elif clicked_editor_button_label == "Delete File":
                # Confirmation for delete
                if 'confirm_delete_pending' not in st.session_state:
                    st.session_state.confirm_delete_pending = True
                    st.rerun() # Rerun to show confirmation

            if st.session_state.get('confirm_delete_pending'):
                st.warning(f"Are you sure you want to delete `{selected_filename_for_editor}`? This cannot be undone.")
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    if st.button(f"Yes, Delete `{selected_filename_for_editor}`", type="primary", use_container_width=True, key="confirm_delete_yes"):
                        if delete_file_from_workspace(selected_filename_for_editor, WORKSPACE_DIR):
                            app_logger.info(f"User deleted file: {selected_filename_for_editor}")
                            # If the deleted file was being previewed, stop the preview
                            if st.session_state.preview_file == selected_filename_for_editor:
                                stop_preview() # This clears preview state

                            # Clear editor state as file is gone
                            st.session_state.selected_file = None
                            st.session_state.file_content_on_load = ""
                            st.session_state.editor_unsaved_content = ""
                            st.session_state.last_saved_content = ""
                        # else: delete_file_from_workspace shows errors
                        del st.session_state.confirm_delete_pending
                        st.rerun() # Update file list and editor view
                with cancel_col:
                    if st.button("Cancel Deletion", use_container_width=True, key="confirm_delete_no"):
                        del st.session_state.confirm_delete_pending
                        st.rerun()


        else: # No file selected for editor
            st.info("Select a Python file from the list on the left to view or edit its content.")
            # Display a read-only placeholder in the editor area
            st_ace(
                value="# No file selected.\n\n# Please choose a file from the 'Project Files' list.",
                language="python",
                theme=ACE_DEFAULT_THEME,
                keybinding=ACE_DEFAULT_KEYBINDING,
                font_size=ACE_FONT_SIZE,
                readonly=True,
                height=500,
                key="ace_editor_placeholder"
            )

# --- Live Preview Tab ---
elif selected_tab == "Live Preview":
    st.header("▶️ Live Preview")
    st.warning("⚠️ Running AI-generated code can have unintended consequences. Always review the code in the 'Workspace & Editor' tab before running a preview!", icon="❗")

    is_preview_running = st.session_state.get("preview_process") is not None
    file_being_previewed = st.session_state.get("preview_file")
    preview_url = st.session_state.get("preview_url")
    # File selected in Workspace tab, which is the candidate for previewing
    candidate_file_for_preview = st.session_state.get("selected_file")

    st.subheader("Preview Controls")
    if not candidate_file_for_preview:
        st.info("To run a preview, first select a Python file in the 'Workspace & Editor' tab.")
    else:
        st.write(f"File selected for preview actions: `{candidate_file_for_preview}`")
        if not candidate_file_for_preview.endswith(".py"):
            st.error("Cannot preview: Selected file is not a Python (.py) file.")
        else:
            # Layout Run and Stop buttons
            run_col, stop_col = st.columns(2)
            with run_col:
                # Disable Run button if a preview is already running for *any* file,
                # or if the candidate file is not valid.
                run_disabled = is_preview_running or not candidate_file_for_preview
                if st.button("🚀 Run Preview", disabled=run_disabled, type="primary", use_container_width=True, key="run_preview_button"):
                    if start_preview(candidate_file_for_preview): # This updates session state
                        st.rerun() # Rerun to show the preview iframe and update button states
                    # else: start_preview shows errors

            with stop_col:
                # Disable Stop button if no preview is running OR if the running preview
                # is for a DIFFERENT file than the one currently selected as candidate.
                # This logic allows stopping the *current* preview even if another file is selected in workspace.
                stop_disabled = not is_preview_running
                button_label = f"⏹️ Stop Preview ({file_being_previewed})" if is_preview_running else "⏹️ Stop Preview"

                if st.button(button_label, disabled=stop_disabled, use_container_width=True, key="stop_preview_button"):
                    stop_preview() # This updates session state
                    st.rerun() # Rerun to remove iframe and update button states

    st.markdown("---")
    st.subheader("Preview Window")
    if is_preview_running and file_being_previewed:
        # Check if the live process is still running before attempting to show iframe
        live_process = st.session_state.preview_process
        if live_process and live_process.poll() is None: # Process is alive
            st.info(f"Showing live preview for: `{file_being_previewed}`")
            st.caption(f"Access URL: {preview_url} (if running locally and firewall permits)")
            st.components.v1.iframe(preview_url, height=600, scrolling=True)
        else: # Process died or was stopped, but state not fully cleared yet
            st.warning(f"Preview for `{file_being_previewed}` is not active or stopped unexpectedly.")
            app_logger.warning(f"Preview process for '{file_being_previewed}' found dead or stopped when trying to display iframe.")
            # Attempt to show error output if available from the dead process
            if live_process:
                try:
                    stdout_output = live_process.stdout.read() if live_process.stdout else ""
                    stderr_output = live_process.stderr.read() if live_process.stderr else ""
                    if stdout_output or stderr_output:
                        with st.expander("Show Output from Stopped Preview Process", expanded=False):
                            if stdout_output: st.code(stdout_output, language=None, line_numbers=True)
                            if stderr_output: st.code(stderr_output, language=None, line_numbers=True)
                except Exception as read_err:
                    app_logger.error(f"Could not read output from stopped preview process: {read_err}")

            # Ensure preview state is fully cleared if process is dead
            if st.session_state.preview_process: # Check again, stop_preview might be called by other logic
                stop_preview() # This will clear state
                st.rerun() # Rerun to reflect cleared state
    else:
        st.info("No live preview is currently running. Select a Python file and click 'Run Preview' to see it here.")

# --- Footer (Optional) ---
st.markdown("---")
st.caption("Streamlit AI App Generator - Pro Edition | Powered by Google Gemini")

