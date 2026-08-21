from conftest import seed_merchant_context, trigger_payload
from vera.context.store import ContextStore
from vera.domain.enums import ConversationStatus, SuppressionReason
from vera.domain.models import ConversationState
from vera.policy.suppression import SuppressionRegistry


def get_trigger(store, payload=None):
    seed_merchant_context(store)
    payload = payload or trigger_payload(event_payload={"metric": "views", "delta_pct": -10, "window": "7d"})
    store.put("trigger", payload["id"], 1, payload)
    return store.get_trigger(payload["id"])


def test_suppression_blocks_duplicate_trigger_in_conversation(now):
    store = ContextStore()
    trigger = get_trigger(store)
    state = ConversationState("conv-1", "m-1", None, sent_trigger_ids=(trigger.trigger_id,))

    decision = SuppressionRegistry().evaluate(trigger, "m-1", None, now, state)

    assert not decision.allowed
    assert decision.reason == SuppressionReason.DUPLICATE_IN_CONVERSATION


def test_suppression_blocks_terminal_conversation(now):
    store = ContextStore()
    trigger = get_trigger(store)
    state = ConversationState("conv-1", "m-1", None, status=ConversationStatus.COMPLETED)

    decision = SuppressionRegistry().evaluate(trigger, "m-1", None, now, state)

    assert not decision.allowed
    assert decision.reason == SuppressionReason.CONVERSATION_TERMINAL


def test_suppression_blocks_expired_trigger(now):
    store = ContextStore()
    trigger = get_trigger(
        store,
        trigger_payload(
            expires_at="2026-04-26T09:59:00Z",
            event_payload={"metric": "views", "delta_pct": -10, "window": "7d"},
        ),
    )

    decision = SuppressionRegistry().evaluate(trigger, "m-1", None, now)

    assert not decision.allowed
    assert decision.reason == SuppressionReason.EXPIRED_TRIGGER
