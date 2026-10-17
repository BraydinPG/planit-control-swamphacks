"""Shared test setup.

Tests never reach the real Gemini API, even when backend/.env holds a key: an environment
variable overrides the .env file, so every client built from settings is unconfigured.
Tests that need Gemini inject a fake transport.
"""

import os

os.environ["GEMINI_API_KEY"] = ""
