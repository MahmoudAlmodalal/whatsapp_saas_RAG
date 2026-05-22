"""Compatibility shim for the root-level Celery app."""

from celery_app import celery_app

__all__ = ["celery_app"]
