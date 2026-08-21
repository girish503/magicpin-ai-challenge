from conftest import seed_merchant_context, trigger_payload
from vera.context.resolver import ContextResolver
from vera.context.store import ContextStore
from vera.decision.opportunity import get_rule
from vera.domain.enums import ContextScope, TargetScope
from vera.domain.models import Fact
from vera.messaging.message_plan import build_message_plan


def test_message_plan_contains_provenance_and_no_body():
    store = ContextStore()
    seed_merchant_context(store)
    payload = trigger_payload(
        event_payload={"metric": "views", "delta_pct": -10, "window": "7d"}
    )
    store.put("trigger", payload["id"], 1, payload)
    resolved = ContextResolver(store).resolve(None, "m-1", store.get_trigger("t-1"))
    facts = (Fact(ContextScope.TRIGGER, "t-1", "payload.metric", "views"),)

    plan = build_message_plan(resolved, get_rule("perf_dip"), facts, None, 42, (("evidence", "3"),))

    assert plan.should_send
    assert plan.target_scope == TargetScope.MERCHANT
    assert plan.send_as == "vera"
    assert plan.selected_facts == facts
    assert not hasattr(plan, "body")
    assert ("opportunity_score", "42") in plan.decision_metadata


def test_customer_message_plan_uses_merchant_on_behalf():
    store = ContextStore()
    seed_merchant_context(store)
    customer = {
        "customer_id": "c-1",
        "merchant_id": "m-1",
        "identity": {"name": "Asha", "language_pref": "en"},
        "preferences": {"reminder_opt_in": True},
        "consent": {"opted_in_at": "2026-04-01T09:00:00Z", "scope": ["appointment_reminders"]},
        "state": "active",
    }
    store.put("customer", "c-1", 1, customer)
    payload = trigger_payload(
        kind="appointment_tomorrow",
        scope="customer",
        customer_id="c-1",
        event_payload={"available_slots": ["10:00"]},
    )
    store.put("trigger", payload["id"], 1, payload)
    resolved = ContextResolver(store).resolve(None, "m-1", store.get_trigger("t-1"), "c-1")

    plan = build_message_plan(resolved, get_rule("appointment_tomorrow"), (), None, 10, ())

    assert plan.target_scope == TargetScope.CUSTOMER
    assert plan.customer_id == "c-1"
    assert plan.send_as == "merchant_on_behalf"
