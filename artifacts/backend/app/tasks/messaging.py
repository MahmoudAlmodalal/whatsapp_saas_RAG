"""Compatibility shim for the root-level inbound message task."""

from tasks.message_tasks import process_inbound_message

__all__ = ["process_inbound_message"]
