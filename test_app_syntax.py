"""Catch syntax errors in the deployed Streamlit entry point without importing it."""
from pathlib import Path
import unittest


class AppSyntaxTests(unittest.TestCase):
    def test_app_compiles(self):
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        compile(source, "app.py", "exec")


if __name__ == "__main__":
    unittest.main()
