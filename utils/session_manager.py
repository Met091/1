# utils/session_manager.py
import streamlit as st
from utils.logger import app_logger

def initialize_session_state():
    """
    Sets up default values in Streamlit's session state dictionary.
    This function should be called once at the beginning of the app script.
    """
    state_defaults = {
        "messages": [],             # List to store chat messages (user and AI)
        "selected_file": None,      # Name of the file currently shown in the editor
        "file_content_on_load": "", # Content of the selected file when loaded (read-only at load)
        "preview_process": None,    # Stores the running preview subprocess object
        "preview_port": None,       # Port number used by the preview
        "preview_url": None,        # URL to access the preview
        "preview_file": None,       # Name of the file being previewed
        "editor_unsaved_content": "", # Current text typed into the editor by the user
        "last_saved_content": "",   # Content that was last successfully saved to disk (by user or AI)
        "ai_is_thinking": False,    # Flag to manage AI processing state
    }

    # Initialize only if keys are not already present
    for key, default_value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
            app_logger.debug(f"Initialized session state key '{key}' with default value.")

    app_logger.info("Session state initialized or verified.")

if __name__ == "__main__":
    # This part is for testing the module independently if needed
    # In a Streamlit app, this would be run as part of the app script.
    # To test, you'd run `python utils/session_manager.py` but it won't do much
    # without the Streamlit context.
    app_logger.info("Session manager module loaded. Call initialize_session_state() within a Streamlit app.")
