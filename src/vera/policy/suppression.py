from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from vera.context.validation import parse_iso8601
from vera.domain.enums import ConversationStatus, SuppressionReason
from vera.domain.models import ConversationState, SuppressionDecision, TriggerContext


@dataclass(frozen=True)
class SuppressionPolicy:
    """`window=None` deliberately means no invented duration; records persist."""

    window: Optional[timedelta] = None


@dataclass(frozen=True)
class SuppressionRecord:
    suppression_key: str
    merchant_id: str
    customer_id: Optional[str]
    trigger_id: str
    recorded_at: datetime


class SuppressionRegistry:
    def __init__(self, policy: SuppressionPolicy | None = None) -> None:
        self.policy = policy or SuppressionPolicy()
        self._records: Dict[Tuple[str, str, Optional[str]], SuppressionRecord] = {}

    def evaluate(
        self,
        trigger: TriggerContext,
        merchant_id: str,
        customer_id: Optional[str],
        now: datetime,
        conversation: Optional[ConversationState] = None,
    ) -> SuppressionDecision:
        if parse_iso8601(trigger.expires_at) <= now:
            return SuppressionDecision(False, SuppressionReason.EXPIRED_TRIGGER, "trigger expiry has passed")
        if conversation is not None:
            if conversation.status in {ConversationStatus.COMPLETED, ConversationStatus.SUPPRESSED}:
                return SuppressionDecision(False, SuppressionReason.CONVERSATION_TERMINAL, "conversation is terminal")
            if trigger.trigger_id in conversation.sent_trigger_ids:
                return SuppressionDecision(False, SuppressionReason.DUPLICATE_IN_CONVERSATION, "trigger was already sent in this conversation")
        key = (trigger.suppression_key, merchant_id, customer_id)
        existing = self._records.get(key)
        if existing is not None and self._is_active(existing, now):
            return SuppressionDecision(False, SuppressionReason.RECORDED_SUPPRESSION_KEY, "suppression key is already recorded")
        return SuppressionDecision(True, SuppressionReason.ALLOWED, "no active suppression applies")

    def mark_sent(self, trigger: TriggerContext, merchant_id: str, customer_id: Optional[str], now: datetime) -> None:
        key = (trigger.suppression_key, merchant_id, customer_id)
        self._records[key] = SuppressionRecord(
            suppression_key=trigger.suppression_key,
            merchant_id=merchant_id,
            customer_id=customer_id,
            trigger_id=trigger.trigger_id,
            recorded_at=now,
        )

    def clear(self, suppression_key: str, merchant_id: str, customer_id: Optional[str]) -> None:
        self._records.pop((suppression_key, merchant_id, customer_id), None)

    def _is_active(self, record: SuppressionRecord, now: datetime) -> bool:
        if self.policy.window is None:
            return True
        return now < record.recorded_at + self.policy.window
