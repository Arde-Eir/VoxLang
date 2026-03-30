"""
VoxLang — Vercel Serverless Entry Point
Wraps the FastAPI app for @vercel/python deployment.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.main import app