# services/preview_service.py
import streamlit as st
import subprocess
import socket
import sys
import time
from pathlib import Path
from utils.logger import app_logger
from config.settings import (
    WORKSPACE_DIR, PREVIEW_SERVER_STARTUP_TIMEOUT,
    PREVIEW_PROCESS_TERMINATE_TIMEOUT, PREVIEW_PROCESS_KILL_TIMEOUT
)

def _find_available_port(start_port: int = 8502, max_attempts: int = 100) -> int | None:
    """
    Finds an unused network port, starting from start_port.

    Args:
        start_port (int): The port number to start checking from.
        max_attempts (int): Maximum number of ports to check.

    Returns:
        int | None: An available port number, or None if no port is found.
    """
    for i in range(max_attempts):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port)) # Try to bind to the port
                app_logger.info(f"Found available port: {port}")
                return s.getsockname()[1]
        except OSError: # Port is likely in use
            app_logger.debug(f"Port {port} is in use, trying next.")
            continue
    app_logger.error(f"Could not find an available port after {max_attempts} attempts starting from {start_port}.")
    return None


def stop_preview():
    """
    Stops the currently running Streamlit preview process stored in session state.
    Updates session state to reflect that no preview is running.
    """
    process_to_stop = st.session_state.get("preview_process")
    pid = getattr(process_to_stop, 'pid', None)
    preview_file = st.session_state.get("preview_file", "unknown file")

    if process_to_stop and pid:
        app_logger.info(f"Attempting to stop preview process (PID: {pid}) for file '{preview_file}'.")
        try:
            if process_to_stop.poll() is None: # Process is still running
                process_to_stop.terminate() # Ask politely first
                try:
                    process_to_stop.wait(timeout=PREVIEW_PROCESS_TERMINATE_TIMEOUT)
                    st.toast(f"Preview for '{preview_file}' (PID: {pid}) stopped.", icon="⏹️")
                    app_logger.info(f"Preview process {pid} for '{preview_file}' terminated gracefully.")
                except subprocess.TimeoutExpired:
                    app_logger.warning(f"Preview process {pid} for '{preview_file}' did not terminate gracefully, killing...")
                    if process_to_stop.poll() is None: # Check again before kill
                        process_to_stop.kill()
                        process_to_stop.wait(timeout=PREVIEW_PROCESS_KILL_TIMEOUT) # Brief wait for kill
                        st.toast(f"Preview for '{preview_file}' (PID: {pid}) forcefully killed.", icon="💀")
                        app_logger.info(f"Preview process {pid} for '{preview_file}' killed.")
            else:
                app_logger.warning(f"Preview process {pid} for '{preview_file}' had already stopped (poll result: {process_to_stop.poll()}).")
        except ProcessLookupError: # Process already gone
            app_logger.warning(f"Preview process {pid} for '{preview_file}' not found (already gone?).")
        except Exception as e:
            st.error(f"Error trying to stop preview process {pid} for '{preview_file}': {e}")
            app_logger.error(f"Error stopping preview process {pid} for '{preview_file}': {e}", exc_info=True)
    elif process_to_stop:
        app_logger.warning(f"Preview process object exists for '{preview_file}' but has no PID, cannot stop reliably.")
    else:
        app_logger.info("No active preview process found to stop.")


    # Always clear the preview state variables after attempting to stop
    st.session_state.preview_process = None
    st.session_state.preview_port = None
    st.session_state.preview_url = None
    st.session_state.preview_file = None
    app_logger.info("Preview session state cleared.")
    # st.rerun() # Rerun should be called by the UI logic in app.py after this function returns

def start_preview(python_filename: str) -> bool:
    """
    Starts a Streamlit app preview for the given Python file in a separate process.
    Updates session state with preview details if successful.

    Args:
        python_filename (str): The name of the Python file in the workspace to preview.

    Returns:
        bool: True if the preview started successfully, False otherwise.
    """
    filepath = WORKSPACE_DIR / python_filename
    if not filepath.is_file() or filepath.suffix != '.py':
        st.error(f"Cannot preview: '{python_filename}' is not a valid Python file or does not exist.")
        app_logger.error(f"Preview attempt for invalid file: {filepath}")
        return False

    # Stop any currently running preview first
    if st.session_state.get("preview_process"):
        st.warning("Stopping existing preview first...")
        app_logger.info("Existing preview found, stopping it before starting new one.")
        stop_preview() # This function updates session state but doesn't rerun
        # A small delay might be beneficial here to ensure the port is released,
        # though _find_available_port should handle finding a new one.
        time.sleep(0.5) # Brief pause

    with st.spinner(f"Starting preview for `{python_filename}`..."):
        try:
            port = _find_available_port()
            if port is None:
                st.error("Failed to find an available port for the preview.")
                app_logger.error("No available port found for starting preview.")
                return False

            # Command to run: python -m streamlit run <filepath> --server.port <port> [options]
            command = [
                sys.executable, # Use the same Python interpreter running this script
                "-m", "streamlit", "run",
                str(filepath.resolve()), # Absolute path to the file
                "--server.port", str(port),
                "--server.headless", "true",    # Don't open a browser automatically
                "--server.runOnSave", "false",  # Don't automatically rerun on save from its own watcher
                "--server.fileWatcherType", "none", # Disable Streamlit's internal file watcher
                "--client.toolbarMode", "minimal" # Keep preview toolbar minimal
            ]
            app_logger.info(f"Starting preview with command: {' '.join(command)}")

            # Start the command as a new process
            # Use Popen for non-blocking execution.
            # Capture stdout/stderr to diagnose issues if preview fails to start.
            preview_proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # Decodes stdout/stderr to text
                encoding='utf-8',
                # creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 # Optional: hide console on Windows
            )

            # Give Streamlit a moment to start up or fail
            time.sleep(PREVIEW_SERVER_STARTUP_TIMEOUT)

            # Check if the process started successfully (is still running)
            if preview_proc.poll() is None: # poll() returns None if process is running
                st.session_state.preview_process = preview_proc
                st.session_state.preview_port = port
                # For Streamlit Cloud, localhost might not be accessible directly in iframe.
                # However, for local dev, this is standard. Streamlit handles its own proxying.
                st.session_state.preview_url = f"http://localhost:{port}"
                st.session_state.preview_file = python_filename
                st.success(f"Preview for '{python_filename}' started: {st.session_state.preview_url}")
                st.toast(f"Preview running for {python_filename}", icon="🚀")
                app_logger.info(f"Preview started for '{python_filename}' on port {port} (PID: {preview_proc.pid}). URL: {st.session_state.preview_url}")
                return True
            else: # Process ended quickly, likely an error
                st.error(f"Preview failed to start for `{python_filename}` (Process exited with code: {preview_proc.poll()}).")
                app_logger.error(f"Preview process for '{python_filename}' failed to start or exited prematurely (code: {preview_proc.poll()}).")
                try:
                    # Capture and display stderr/stdout from the failed process
                    stdout_output = preview_proc.stdout.read() if preview_proc.stdout else ""
                    stderr_output = preview_proc.stderr.read() if preview_proc.stderr else ""
                    if stdout_output:
                        app_logger.error(f"Preview STDOUT for '{python_filename}':\n{stdout_output}")
                        with st.expander("Show Preview Process Output (stdout)", expanded=False):
                            st.code(stdout_output, language=None)
                    if stderr_output:
                        app_logger.error(f"Preview STDERR for '{python_filename}':\n{stderr_output}")
                        with st.expander("Show Preview Process Error Output (stderr)", expanded=True): # Expand errors by default
                            st.code(stderr_output, language=None)
                    if not stdout_output and not stderr_output:
                         st.info("No output captured from the preview process.")
                except Exception as read_e:
                    st.error(f"Could not read output from failed preview process: {read_e}")
                    app_logger.error(f"Error reading output from failed preview process for '{python_filename}': {read_e}", exc_info=True)
                # Clear any partial state
                st.session_state.preview_process = None
                return False
        except Exception as e:
            st.error(f"An unexpected error occurred while trying to start preview for '{python_filename}': {e}")
            app_logger.error(f"Error starting preview process for '{python_filename}': {e}", exc_info=True)
            st.session_state.preview_process = None # Ensure clean state
            return False

if __name__ == "__main__":
    # This module is primarily used within a Streamlit app context.
    # Standalone testing would require mocking st.session_state and UI elements.
    app_logger.info("Preview service module loaded.")
    # Example:
    # if _find_available_port():
    #     app_logger.info("Port finding seems to work.")
    # else:
    #     app_logger.error("Port finding failed.")
