# config/settings.py
import os
from dotenv import load_dotenv
from pathlib import Path
from utils.logger import app_logger
from google.generativeai.types import HarmCategory, HarmBlockThreshold # Import enums

# --- Environment Variables ---
dotenv_path = Path('.') / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    app_logger.info(f".env file found and loaded from {dotenv_path.resolve()}")
else:
    app_logger.warning(f".env file NOT FOUND at {dotenv_path.resolve()}. Relying on environment variables or Streamlit secrets.")

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY and len(GOOGLE_API_KEY) > 10:
    app_logger.info(f"GOOGLE_API_KEY loaded from environment. Length: {len(GOOGLE_API_KEY)}. Starts with: {GOOGLE_API_KEY[:4]}...")
elif GOOGLE_API_KEY:
     app_logger.warning(f"GOOGLE_API_KEY loaded, but it's very short. Length: {len(GOOGLE_API_KEY)}. This might be an issue.")
else:
    app_logger.error("GOOGLE_API_KEY is NOT FOUND in environment variables or .env file. AI features will fail.")


# --- Workspace Configuration ---
WORKSPACE_DIR_NAME = "workspace_st_apps"
WORKSPACE_DIR = Path(WORKSPACE_DIR_NAME)
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
GEMINI_MODEL_NAME = "gemini-1.5-pro-latest"

# --- Gemini API Generation Configuration ---
GEMINI_GENERATION_CONFIG = {
    "temperature": 0.4,
    "top_p": 1.0,
    "top_k": 32,
    "max_output_tokens": 8192,
}

# --- Gemini API Safety Settings (Using Enums for robustness) ---
GEMINI_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}
app_logger.info(f"Gemini Safety Settings configured: { {category.name: threshold.name for category, threshold in GEMINI_SAFETY_SETTINGS.items()} }")


# --- System Prompt for Gemini AI ---
# Note the use of {{ and }} for literal braces that are part of the JSON examples.
# The {file_list} placeholder for .format() is correctly single-braced within the f-string context,
# which means it needs to be {{file_list}} if this entire block was NOT an f-string itself but just a regular string.
# Since it IS an f-string, {file_list} is fine if 'file_list' is a variable available at f-string definition.
# However, we are using .format() later, so the placeholder for .format() should be single braces.
# The f-string itself should escape literal braces.

# To clarify:
# 1. This string is defined as an f-string (starts with f""").
# 2. Placeholders for .format() method (like {file_list}) should be single-braced.
# 3. Literal curly braces that are part of the text (like in JSON examples) MUST be doubled ({{ or }})
#    to distinguish them from f-string interpolation placeholders.

GEMINI_SYSTEM_PROMPT_TEMPLATE = f"""
You are an AI assistant specialized in creating and managing Python files for Streamlit applications.
Your primary goal is to accurately interpret user requests and translate them into file operations within a designated workspace.
Respond *only* with a valid JSON array of command objects. Do not include any explanatory text, markdown formatting (like ```json), or any other content outside of this JSON array.

Available commands:
1.  `{{{{\"action\": \"create_update\", \"filename\": \"app_name.py\", \"content\": \"FULL_PYTHON_CODE_HERE\"}}}}`
    - Use this command to create a new Python file or completely overwrite an existing one.
    - The "filename" must be a valid Python file name (e.g., `my_app.py`).
    - The "content" must be the *complete and entire* Python code for the file.
    - Ensure all special characters in the "content" string are properly escaped for JSON:
        - Backslashes (`\\`) must be escaped as `\\\\`.
        - Double quotes (`"`) must be escaped as `\\\"`.
        - Newlines must be represented as `\\n`.
    - Do *not* include ```python markdown blocks or shebangs (`#!/usr/bin/env python`) in the "content" field.

2.  `{{{{\"action\": \"delete\", \"filename\": \"old_app.py\"}}}}`
    - Use this command to delete a specified Python file from the workspace.
    - The "filename" must be the exact name of the file to be deleted.

3.  `{{{{\"action\": \"chat\", \"content\": \"Your message here.\"}}}}`
    - Use this command *only* if:
        - You need to ask for clarification on an ambiguous user request.
        - You encounter an issue you cannot resolve with file actions (e.g., a conceptual problem with the request).
        - You need to confirm understanding before performing a significant or destructive action.
        - You want to provide a status update or a simple acknowledgement.

Current Python files in workspace: {{file_list}}

Example Interaction:
User: Create a simple hello world app called hello.py
AI: `[{{{{\"action\": \"create_update\", \"filename\": \"hello.py\", \"content\": \"import streamlit as st\\n\\nst.title('Hello World!')\\nst.write('This is a simple app.')\"}}}}]`

User: Delete the app named old_app.py
AI: `[{{{{\"action\": \"delete\", \"filename\": \"old_app.py\"}}}}]`

User: I'm not sure what to do next.
AI: `[{{{{\"action\": \"chat\", \"content\": \"I can help you create or modify Streamlit apps. What would you like to build today?\"}}}}]`

Important Rules:
- Your entire response *must* be a single JSON array `[...]`.
- Do not add any text before or after the JSON array.
- If multiple actions are needed for a single user request (e.g., delete one file and create another), include them as separate command objects within the same JSON array.
- Adhere strictly to the command formats specified.
"""

# --- Preview Server Configuration ---
PREVIEW_SERVER_STARTUP_TIMEOUT = 5
PREVIEW_PROCESS_TERMINATE_TIMEOUT = 3
PREVIEW_PROCESS_KILL_TIMEOUT = 2

app_logger.info("Configuration settings module processed.")

