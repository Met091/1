# utils/file_utils.py
import os
from pathlib import Path
import streamlit as st # For st.error/warning/toast in user-facing messages
from utils.logger import app_logger
# WORKSPACE_DIR is imported where needed or passed as an argument.
# from config.settings import WORKSPACE_DIR # Avoid circular import if utils are used by config

def get_workspace_python_files(workspace_dir: Path) -> list[str]:
    """
    Gets a sorted list of all '.py' filenames in the specified workspace directory.

    Args:
        workspace_dir (Path): The path to the workspace directory.

    Returns:
        list[str]: A list of Python filenames, sorted alphabetically.
                   Returns an empty list if the directory doesn't exist or on error.
    """
    if not workspace_dir.is_dir():
        app_logger.warning(f"Workspace directory '{workspace_dir}' not found or is not a directory.")
        return []
    try:
        python_files = sorted([
            f.name for f in workspace_dir.iterdir()
            if f.is_file() and f.suffix == '.py'
        ])
        app_logger.debug(f"Found Python files in '{workspace_dir}': {python_files}")
        return python_files
    except Exception as e:
        st.error(f"Error reading workspace directory: {e}")
        app_logger.error(f"Error reading workspace directory '{workspace_dir}': {e}", exc_info=True)
        return []

def read_file(filename: str, workspace_dir: Path) -> str | None:
    """
    Reads the text content of a file from the workspace.

    Args:
        filename (str): The name of the file to read.
        workspace_dir (Path): The path to the workspace directory.

    Returns:
        str | None: The file's text content, or None if the file is not found,
                    the filename is invalid, or an error occurs.
    """
    if not filename:
        app_logger.warning("Read attempt with no filename provided.")
        return None
    # Basic security check to prevent path traversal
    if ".." in filename or filename.startswith(("/", "\\")):
        st.error(f"Invalid file path: {filename}")
        app_logger.error(f"Invalid file path attempted for reading: {filename}")
        return None

    filepath = workspace_dir / filename
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        app_logger.info(f"File '{filepath}' read successfully.")
        return content
    except FileNotFoundError:
        st.warning(f"File not found: {filename}")
        app_logger.warning(f"File not found during read attempt: {filepath}")
        return None
    except Exception as e:
        st.error(f"Error reading file '{filename}': {e}")
        app_logger.error(f"Error reading file '{filepath}': {e}", exc_info=True)
        return None

def save_file(filename: str, content: str, workspace_dir: Path) -> bool:
    """
    Writes text content to a file in the workspace. Overwrites if the file exists.

    Args:
        filename (str): The name of the file to save.
        content (str): The text content to write to the file.
        workspace_dir (Path): The path to the workspace directory.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    if not filename:
        app_logger.warning("Save attempt with no filename provided.")
        st.error("Cannot save: Filename is missing.")
        return False
    if ".." in filename or filename.startswith(("/", "\\")):
        st.error(f"Invalid file path: {filename}")
        app_logger.error(f"Invalid file path attempted for saving: {filename}")
        return False
    if not filename.endswith(".py"): # Enforce .py extension
        st.error(f"Invalid filename: '{filename}'. Must end with '.py'.")
        app_logger.error(f"Save attempt with invalid extension: {filename}")
        return False


    filepath = workspace_dir / filename
    try:
        # Ensure the workspace directory exists (it should, but double-check)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        app_logger.info(f"File '{filepath}' saved successfully.")
        return True
    except Exception as e:
        st.error(f"Error saving file '{filename}': {e}")
        app_logger.error(f"Error saving file '{filepath}': {e}", exc_info=True)
        return False

def delete_file_from_workspace(filename: str, workspace_dir: Path) -> bool:
    """
    Deletes a file from the workspace.

    Args:
        filename (str): The name of the file to delete.
        workspace_dir (Path): The path to the workspace directory.

    Returns:
        bool: True if deletion was successful or file didn't exist, False on error.
              Note: The original script's delete_file also updated session state.
              This function focuses on the file system operation. Session state updates
              should be handled by the calling function in app.py or service layer.
    """
    if not filename:
        app_logger.warning("Delete attempt with no filename provided.")
        st.error("Cannot delete: Filename is missing.")
        return False
    if ".." in filename or filename.startswith(("/", "\\")):
        st.error(f"Invalid file path: {filename}")
        app_logger.error(f"Invalid file path attempted for deletion: {filename}")
        return False

    filepath = workspace_dir / filename
    try:
        if filepath.is_file():
            os.remove(filepath)
            st.toast(f"Deleted: {filename}", icon="🗑️")
            app_logger.info(f"File '{filepath}' deleted successfully.")
            return True
        else:
            st.warning(f"Could not delete: File '{filename}' not found.")
            app_logger.warning(f"File not found during delete attempt: {filepath}")
            return True # Considered success if file doesn't exist for idempotency
    except Exception as e:
        st.error(f"Error deleting file '{filename}': {e}")
        app_logger.error(f"Error deleting file '{filepath}': {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Example usage (requires a 'test_workspace' directory to be created manually for testing)
    # This is for standalone testing of file_utils.py
    test_ws_dir = Path("test_workspace_fu")
    test_ws_dir.mkdir(exist_ok=True)

    app_logger.info("Testing file_utils.py...")

    # Test save_file
    save_success = save_file("test_app.py", "print('Hello from test_app.py')", test_ws_dir)
    app_logger.info(f"Save 'test_app.py' success: {save_success}")

    save_invalid_name = save_file("../test_app.py", "print('danger')", test_ws_dir)
    app_logger.info(f"Save '../test_app.py' success (should be False): {save_invalid_name}")

    save_no_ext = save_file("test_doc.txt", "print('danger')", test_ws_dir)
    app_logger.info(f"Save 'test_doc.txt' success (should be False): {save_no_ext}")


    # Test get_workspace_python_files
    files = get_workspace_python_files(test_ws_dir)
    app_logger.info(f"Python files in '{test_ws_dir}': {files}")

    # Test read_file
    content = read_file("test_app.py", test_ws_dir)
    if content:
        app_logger.info(f"Content of 'test_app.py':\n{content}")
    else:
        app_logger.warning("Could not read 'test_app.py'")

    # Test delete_file_from_workspace
    # delete_success = delete_file_from_workspace("test_app.py", test_ws_dir)
    # app_logger.info(f"Delete 'test_app.py' success: {delete_success}")

    # files_after_delete = get_workspace_python_files(test_ws_dir)
    # app_logger.info(f"Python files after delete: {files_after_delete}")

    # Clean up test directory (optional)
    # import shutil
    # shutil.rmtree(test_ws_dir)
    # app_logger.info(f"Cleaned up test directory: {test_ws_dir}")
