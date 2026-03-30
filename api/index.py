"""
VoxLang — Vercel Serverless Entry Point
Wraps the FastAPI app for @vercel/python deployment.
"""
import sys, os

# Add project root so shared/ and backend/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.main import app  # noqa — Vercel expects `app` at module level