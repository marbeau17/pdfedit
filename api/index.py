"""Vercel serverless function entry point."""
import os
import sys

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402, F401

# Vercel expects the app to be accessible as `app`
