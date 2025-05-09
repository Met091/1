# config/settings.py
import os
from dotenv import load_dotenv
from pathlib import Path
from utils.logger import app_logger

# --- Environment Variables ---
# Load environment variables from .env file in the project root
# The .env file should be in the same directory as app.py or the project root.
# For Streamlit Cloud, secrets are set in the dashboard.
dotenv_path = Path('.') / '.env' # Assumes .env is in the root of the project
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    app_logger.info(f".env file loaded from {dotenv_path.resolve()}")
else:
    app_logger.info(".env file not found, relying on Streamlit secrets or environment variables.")

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    app_logger.warning("GOOGLE_API_KEY not found in environment variables or .env file.")
    # In a Streamlit app, st.error() would be used in app.py if this is critical at startup.

# --- Workspace Configuration ---
# Defines the directory where AI-generated Streamlit app files will be saved.
# Path is relative to the project root (where app.py is located).
WORKSPACE_DIR_NAME = "workspace_st_apps"
WORKSPACE_DIR = Path(WORKSPACE_DIR_NAME)
# Ensure the directory exists when the settings module is loaded.
try:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    app_logger.info(f"Workspace directory '{WORKSPACE_DIR.resolve()}' ensured.")
except Exception as e:
    app_logger.error(f"Could not create workspace directory '{WORKSPACE_DIR.resolve()}': {e}", exc_info=True)


# --- Code Editor Appearance Settings (for streamlit-ace) ---
ACE_DEFAULT_THEME = "monokai"
ACE_DEFAULT_KEYBINDING = "vscode"
ACE_FONT_SIZE = 14
ACE_TAB_SIZE = 4
ACE_WRAP_LINES = True

# --- AI Model Configuration ---
# Specifies which Google AI model to use for generating code.
# Ensure this model is available and supports the required features.
# GEMINI_MODEL_NAME = "gemini-1.5-flash-latest" # A faster, more cost-effective option
GEMINI_MODEL_NAME = "gemini-1.5-pro-latest" # A more capable model

# --- Gemini API Generation Configuration ---
# These settings control aspects of the AI's response generation.
# Adjust as needed for desired output behavior.
# Refer to Google AI documentation for details on these parameters.
GEMINI_GENERATION_CONFIG = {
    "temperature": 0.4,       # Controls randomness. Lower is more deterministic.
    "top_p": 1.0,             # Nucleus sampling.
    "top_k": 32,              # Limits the sampling pool.
    "max_output_tokens": 8192,# Maximum number of tokens in the response.
}

# --- Gemini API Safety Settings ---
# Configure content safety thresholds.
# Options: BLOCK_NONE, BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE
# It's crucial to understand the implications of these settings.
GEMINI_SAFETY_SETTINGS = {
    "HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
    "HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
    "SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
    "DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
}


# --- System Prompt for Gemini AI ---
# This template instructs the AI on its role, available commands, and response format.
# The `{file_list}` placeholder will be dynamically filled with the current files in the workspace.
GEMINI_SYSTEM_PROMPT_TEMPLATE = f"""
You are an AI assistant specialized in creating and managing Python files for Streamlit applications.
Your primary goal is to accurately interpret user requests and translate them into file operations within a designated workspace.
Respond *only* with a valid JSON array of command objects. Do not include any explanatory text, markdown formatting (like ```json), or any other content outside of this JSON array.

Available commands:
1.  `{{"action": "create_update", "filename": "app_name.py", "content": "FULL_PYTHON_CODE_HERE"}}`
    - Use this command to create a new Python file or completely overwrite an existing one.
    - The "filename" must be a valid Python file name (e.g., `my_app.py`).
    - The "content" must be the *complete and entire* Python code for the file.
    - Ensure all special characters in the "content" string are properly escaped for JSON:
        - Backslashes (`\\`) must be escaped as `\\\\`.
        - Double quotes (`"`) must be escaped as `\\\"`.
        - Newlines must be represented as `\\n`.
    - Do *not* include ```python markdown blocks or shebangs (`#!/usr/bin/env python`) in the "content" field.

2.  `{{"action": "delete", "filename": "old_app.py"}}`
    - Use this command to delete a specified Python file from the workspace.
    - The "filename" must be the exact name of the file to be deleted.

3.  `{{"action": "chat", "content": "Your message here."}}`
    - Use this command *only* if:
        - You need to ask for clarification on an ambiguous user request.
        - You encounter an issue you cannot resolve with file actions (e.g., a conceptual problem with the request).
        - You need to confirm understanding before performing a significant or destructive action.
        - You want to provide a status update or a simple acknowledgement.

Current Python files in workspace: {{file_list}}

Example Interaction:
User: Create a simple hello world app called hello.py
AI: `[{{"action": "create_update", "filename": "hello.py", "content": "import streamlit as st\\n\\nst.title('Hello World!')\\nst.write('This is a simple app.')"}}`

User: Delete the app named old_app.py
AI: `[{{"action": "delete", "filename": "old_app.py"}}]`

User: I'm not sure what to do next.
AI: `[{{"action": "chat", "content": "I can help you create or modify Streamlit apps. What would you like to build today?"}}]`

Important Rules:
- Your entire response *must* be a single JSON array `[...]`.
- Do not add any text before or after the JSON array.
- If multiple actions are needed for a single user request (e.g., delete one file and create another), include them as separate command objects within the same JSON array.
- Adhere strictly to the command formats specified.
"""

# --- Preview Server Configuration ---
PREVIEW_SERVER_STARTUP_TIMEOUT = 5  # Seconds to wait for preview server to start
PREVIEW_PROCESS_TERMINATE_TIMEOUT = 3 # Seconds to wait for graceful termination
PREVIEW_PROCESS_KILL_TIMEOUT = 2      # Seconds to wait after kill signal

app_logger.info("Configuration settings loaded.")

if __name__ == "__main__":
    app_logger.info(f"GOOGLE_API_KEY is set: {bool(GOOGLE_API_KEY)}")
    app_logger.info(f"Workspace directory: {WORKSPACE_DIR.resolve()}")
    app_logger.info(f"Gemini Model: {GEMINI_MODEL_NAME}")
