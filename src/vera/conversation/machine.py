from __future__ import annotations

from dataclasses import replace

from vera.domain.enums import ConversationStatus, Intent
from vera.domain.models import ConversationMessage, ConversationState


class ConversationMachine:
    """Pure state transitions for the later reply endpoint."""

    STOP_TERMS = ("stop", "not interested", "do not message", "don't message", "useless spam")
    AUTO_REPLY_TERMS = ("thank you for contacting", "team will respond", "automated assistant")
    COMMITMENT_TERMS = ("let's do it", "lets do it", "go ahead", "confirm", "yes please", "what's next", "whats next")
    DEFER_TERMS = ("later", "call me", "busy", "wait", "tomorrow")

    @staticmethod
    def new(conversation_id: str, merchant_id: str, customer_id: str | None = None) -> ConversationState:
        return ConversationState(conversation_id=conversation_id, merchant_id=merchant_id, customer_id=customer_id)

    @classmethod
    def record_outbound(cls, state: ConversationState, body: str, trigger_id: str, at: str, turn_number: int) -> ConversationState:
        message = ConversationMessage(from_role="vera", body=body, at=at, turn_number=turn_number)
        sent_trigger_ids = state.sent_trigger_ids if trigger_id in state.sent_trigger_ids else state.sent_trigger_ids + (trigger_id,)
        return replace(
            state,
            status=ConversationStatus.WAITING_FOR_MERCHANT,
            messages=state.messages + (message,),
            last_sent_action="send",
            last_trigger_id=trigger_id,
            sent_trigger_ids=sent_trigger_ids,
            pending_action="await_reply",
            updated_at=at,
        )

    @classmethod
    def receive_reply(cls, state: ConversationState, body: str, at: str, turn_number: int) -> ConversationState:
        intent = cls.detect_intent(state, body)
        message = ConversationMessage(from_role="merchant", body=body, at=at, turn_number=turn_number)
        status, pending = cls._next_status(intent, state, body)
        signals = state.merchant_signals
        if intent == Intent.AUTO_REPLY and "auto_reply" not in signals:
            signals = signals + ("auto_reply",)
        if intent == Intent.STOP and "opt_out" not in signals:
            signals = signals + ("opt_out",)
        return replace(
            state,
            status=status,
            messages=state.messages + (message,),
            merchant_signals=signals,
            current_intent=intent,
            pending_action=pending,
            updated_at=at,
        )

    @classmethod
    def mark_completed(cls, state: ConversationState, at: str) -> ConversationState:
        return replace(state, status=ConversationStatus.COMPLETED, pending_action=None, updated_at=at)

    @classmethod
    def detect_intent(cls, state: ConversationState, body: str) -> Intent:
        text = body.lower().strip()
        if any(term in text for term in cls.STOP_TERMS):
            return Intent.STOP
        if any(term in text for term in cls.AUTO_REPLY_TERMS):
            return Intent.AUTO_REPLY
        if any(term in text for term in cls.COMMITMENT_TERMS):
            return Intent.COMMITMENT
        if any(term in text for term in cls.DEFER_TERMS):
            return Intent.DEFER
        return Intent.UNKNOWN

    @classmethod
    def _next_status(cls, intent: Intent, state: ConversationState, body: str) -> tuple[ConversationStatus, str | None]:
        if intent == Intent.STOP:
            return ConversationStatus.SUPPRESSED, None
        if intent == Intent.COMMITMENT:
            return ConversationStatus.ACTION_READY, "execute_committed_action"
        if intent == Intent.DEFER:
            return ConversationStatus.WAITING_FOR_MERCHANT, "backoff"
        if intent == Intent.AUTO_REPLY:
            repeats = sum(1 for message in state.messages if message.from_role == "merchant" and message.body.strip().lower() == body.strip().lower()) + 1
            if repeats >= 3:
                return ConversationStatus.COMPLETED, None
            return ConversationStatus.WAITING_FOR_MERCHANT, "backoff_auto_reply"
        return ConversationStatus.ACTIVE, "continue_contextually"
