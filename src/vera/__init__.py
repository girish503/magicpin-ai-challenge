"""Deterministic domain core for the Magicpin Vera challenge.

This package deliberately contains no HTTP transport, LLM integration, or
message-body generation. It decides whether a grounded message may be planned.
"""

from vera.decision.ranker import DeterministicRanker

__all__ = ["DeterministicRanker"]
