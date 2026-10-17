"""Shared test setup.

Tests never reach the real Gemini API or live feeds, even when backend/.env holds a key
or turns the feed loop on: an environment variable overrides the .env file. Tests that
need Gemini inject a fake transport; feed tests use fakes.
"""

import os

os.environ["GEMINI_API_KEY"] = ""
# Likewise, starting the app in a test never starts the live feed loop or the 6 PM
# briefing job, whatever backend/.env says.
os.environ["FEED_REFRESH_ENABLED"] = "false"
os.environ["BRIEFING_SCHEDULE_ENABLED"] = "false"
