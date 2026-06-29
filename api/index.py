"""
Vercel serverless entry point for Seven Bet FastAPI app.
"""
import sys
import os

# Ensure the project root is on the path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.main import app