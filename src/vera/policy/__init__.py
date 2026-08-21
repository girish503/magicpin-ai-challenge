"""Deterministic consent, eligibility, and suppression policy."""

from vera.policy.consent import evaluate_customer_consent
from vera.policy.suppression import SuppressionRegistry

__all__ = ["SuppressionRegistry", "evaluate_customer_consent"]
