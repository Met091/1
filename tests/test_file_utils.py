# tests/test_file_utils.py
import unittest
from pathlib import Path
import shutil
import os

# Adjust import path based on how you run tests (e.g., from project root)
# If running `python -m unittest discover tests` from project root:
from utils.file_utils import save_file, read_file, get_workspace_python_files, delete_file_from_workspace
from config.settings import WORKSPACE_DIR # Using the actual workspace for some tests can be tricky, consider a dedicated test workspace

# It's often better to use a temporary directory for file operation tests
TEST_WORKSPACE_NAME = "test_temp_workspace_fu"

class TestFileUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a temporary workspace for tests."""
        cls.test_workspace = Path(TEST_WORKSPACE_NAME)
        if cls.test_workspace.exists():
            shutil.rmtree(cls.test_workspace) # Clean up if exists from previous failed run
        cls.test_workspace.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary workspace after all tests."""
        if cls.test_workspace.exists():
            shutil.rmtree(cls.test_workspace)

    def setUp(self):
        """Clean the test workspace before each test method."""
        for item in self.test_workspace.iterdir():
            if item.is_file():
                os.remove(item)
            elif item.is_dir():
                shutil.rmtree(item)

    def test_01_save_and_read_file(self):
        """Test saving a file and then reading it."""
        filename = "test_app_01.py"
        content = "import streamlit as st\nst.title('Test App 01')"
        
        # Mock st.error, st.warning, st.toast for non-Streamlit environment if they are called
        # For simple tests, we might not need full mocking if logic paths avoid UI calls.
        # However, file_utils directly calls st.error etc.
        # A more robust approach would be to inject a UI notifier object or use a headless UI mock.
        # For this example, we assume these calls won't break the test logic itself.

        save_result = save_file(filename, content, self.test_workspace)
        self.assertTrue(save_result, "File should be saved successfully.")
        
        read_content = read_file(filename, self.test_workspace)
        self.assertEqual(content, read_content, "Read content should match saved content.")

    def test_02_get_workspace_python_files(self):
        """Test listing Python files in the workspace."""
        save_file("app1.py", "print(1)", self.test_workspace)
        save_file("app2.py", "print(2)", self.test_workspace)
        save_file("script.txt", "not python", self.test_workspace) # Non-python file

        py_files = get_workspace_python_files(self.test_workspace)
        self.assertEqual(len(py_files), 2, "Should find two Python files.")
        self.assertIn("app1.py", py_files, "app1.py should be in the list.")
        self.assertIn("app2.py", py_files, "app2.py should be in the list.")
        self.assertNotIn("script.txt", py_files, "script.txt should not be in the list.")
        self.assertEqual(sorted(py_files), ["app1.py", "app2.py"], "Files should be sorted.")

    def test_03_delete_file(self):
        """Test deleting a file."""
        filename = "to_delete.py"
        save_file(filename, "content", self.test_workspace)
        self.assertTrue((self.test_workspace / filename).exists(), "File should exist before delete.")

        delete_result = delete_file_from_workspace(filename, self.test_workspace)
        self.assertTrue(delete_result, "Deletion should be reported as successful.")
        self.assertFalse((self.test_workspace / filename).exists(), "File should not exist after delete.")

        # Test deleting a non-existent file (should also report success for idempotency)
        delete_non_existent = delete_file_from_workspace("non_existent.py", self.test_workspace)
        self.assertTrue(delete_non_existent, "Deleting non-existent file should be 'successful'.")


    def test_04_save_file_invalid_name(self):
        """Test saving a file with an invalid name (path traversal)."""
        # Note: st.error will be called by save_file. In a real test suite, mock it.
        save_result = save_file("../invalid.py", "content", self.test_workspace)
        self.assertFalse(save_result, "Saving with path traversal should fail.")

    def test_05_save_file_no_py_extension(self):
        """Test saving a file without .py extension."""
        save_result = save_file("test_doc.txt", "content", self.test_workspace)
        self.assertFalse(save_result, "Saving without .py extension should fail.")

    def test_06_read_non_existent_file(self):
        """Test reading a file that does not exist."""
        read_content = read_file("ghost.py", self.test_workspace)
        self.assertIsNone(read_content, "Reading a non-existent file should return None.")

if __name__ == '__main__':
    # This allows running tests with `python tests/test_file_utils.py`
    # For Streamlit context dependent functions, this might be limited.
    # Better to run with `python -m unittest discover tests` from project root.
    print(f"Running tests from: {os.getcwd()}")
    print(f"Attempting to import from utils.file_utils. Current sys.path might need adjustment if run directly.")
    unittest.main()
