"""Vercel / uvicorn entrypoint.

  uvicorn main:app --reload
  vercel --prod
"""

from api.main import app

__all__ = ["app"]
