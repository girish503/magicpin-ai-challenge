from conftest import (
    customer_payload,
    seed_customer_context,
    seed_merchant_context,
    trigger_payload,
)
from vera.context.resolver import ContextResolver
from vera.context.store import ContextStore
from vera.domain.enums import ConsentReason, NoActionReason, SuppressionReason
from vera.policy.consent import evaluate_customer_consent
from vera.policy.eligibility import evaluate_trigger_eligibility
from vera.policy.suppression import SuppressionRegistry


def make_context(store, trigger_data, customer=None):
    seed_merchant_context(store)
    if customer is not None:
        seed_customer_context(store, customer)
    store.put("trigger", trigger_data["id"], 1, trigger_data)
    trigger = store.get_trigger(trigger_data["id"])
    resolved = ContextResolver(store).resolve(None, "m-1", trigger, trigger.customer_id)
    return resolved, trigger


def test_merchant_trigger_does_not_require_customer_consent():
    store = ContextStore()
    _, trigger = make_context(
        store,
        trigger_payload(event_payload={"metric": "views", "delta_pct": -10, "window": "7d"}),
    )

    decision = evaluate_customer_consent(trigger, None)

    assert decision.allowed
    assert decision.reason == ConsentReason.NOT_REQUIRED


def test_customer_consent_allows_exact_required_scope():
    store = ContextStore()
    customer = customer_payload(consent_scopes=["appointment_reminders"])
    _, trigger = make_context(
        store,
        trigger_payload(
            kind="appointment_tomorrow",
            scope="customer",
            customer_id="c-1",
            event_payload={"available_slots": ["10:00"]},
        ),
        customer,
    )

    decision = evaluate_customer_consent(trigger, store.get_customer("c-1"))

    assert decision.allowed
    assert decision.matched_scope == "appointment_reminders"


def test_customer_consent_rejects_missing_required_scope():
    store = ContextStore()
    customer = customer_payload(consent_scopes=["promotional_offers"])
    _, trigger = make_context(
        store,
        trigger_payload(
            kind="appointment_tomorrow",
            scope="customer",
            customer_id="c-1",
            event_payload={"available_slots": ["10:00"]},
        ),
        customer,
    )

    decision = evaluate_customer_consent(trigger, store.get_customer("c-1"))

    assert not decision.allowed
    assert decision.reason == ConsentReason.MISSING_REQUIRED_SCOPE


def test_customer_consent_rejects_opt_out_and_reminder_opt_out():
    store = ContextStore()
    customer = customer_payload(consent_scopes=["appointment_reminders"], reminder_opt_in=False)
    _, trigger = make_context(
        store,
        trigger_payload(
            kind="appointment_tomorrow",
            scope="customer",
            customer_id="c-1",
            event_payload={"available_slots": ["10:00"]},
        ),
        customer,
    )

    decision = evaluate_customer_consent(trigger, store.get_customer("c-1"))
    assert decision.reason == ConsentReason.REMINDER_OPT_OUT

    opted_out = customer_payload(consent_scopes=["appointment_reminders"])
    opted_out["consent"]["opted_out"] = True
    assert evaluate_customer_consent(trigger, type(store.get_customer("c-1"))(
        "c-1", 1, opted_out
    )).reason == ConsentReason.OPTED_OUT


def test_placeholder_trigger_is_ineligible(now):
    store = ContextStore()
    resolved, _ = make_context(store, trigger_payload(event_payload={"placeholder": True}))

    result = evaluate_trigger_eligibility(resolved, now)

    assert not result.eligible
    assert result.analysis.no_action_reason == NoActionReason.PLACEHOLDER_EVIDENCE


def test_expired_trigger_is_ineligible(now):
    store = ContextStore()
    resolved, _ = make_context(
        store,
        trigger_payload(
            expires_at="2026-04-26T09:59:00Z",
            event_payload={"metric": "views", "delta_pct": -10, "window": "7d"},
        ),
    )

    result = evaluate_trigger_eligibility(resolved, now)

    assert not result.eligible
    assert result.analysis.no_action_reason == NoActionReason.EXPIRED_TRIGGER


def test_suppression_registry_records_and_deduplicates(now):
    store = ContextStore()
    _, trigger = make_context(
        store,
        trigger_payload(event_payload={"metric": "views", "delta_pct": -10, "window": "7d"}),
    )
    registry = SuppressionRegistry()

    assert registry.evaluate(trigger, "m-1", None, now).allowed
    registry.mark_sent(trigger, "m-1", None, now)
    decision = registry.evaluate(trigger, "m-1", None, now)

    assert not decision.allowed
    assert decision.reason == SuppressionReason.RECORDED_SUPPRESSION_KEY
