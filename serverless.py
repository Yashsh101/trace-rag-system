"""Serverless entry point for Vercel.

Vercel's Python builder resolves the lambda working directory from the
``src`` glob in ``vercel.json``. Importing ``app.main.app`` from inside
``app/`` breaks relative package imports, so this shim lives at the repo
root and re-exports the FastAPI application.
"""

from app.main import app  # noqa: F401

__all__ = ["app"]
