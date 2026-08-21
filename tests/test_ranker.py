from conftest import (
    customer_payload,
    merchant_payload,
    seed_customer_context,
    seed_merchant_context,
    trigger_payload,
)
from vera.context.resolver import ContextResolver
from vera.context.store import ContextStore
from vera.decision.ranker import DeterministicRanker, Opportunity
from vera.domain.enums import DecisionStatus, NoActionReason
from vera.decision.opportunity import get_rule
from vera.domain.models import Fact
from vera.domain.enums import ContextScope


def put_context(store, trigger_data, customer=None, merchant=None):
    merchant = merchant or merchant_payload()
    seed_merchant_context(store, merchant=merchant)
    if customer is not None:
        seed_customer_context(store, customer)
    store.put("trigger", trigger_data["id"], 1, trigger_data)
    return store.get_trigger(trigger_data["id"])


def test_ranker_selects_grounded_merchant_plan(now):
    store = ContextStore()
    trigger = put_context(
        store,
        trigger_payload(event_payload={"metric": "views", "delta_pct": -10, "window": "7d"}),
    )
    result = DeterministicRanker(ContextResolver(store)).decide(None, "m-1", trigger, now)

    assert result.status == DecisionStatus.SELECTED
    assert result.plan.trigger_id == "t-1"
    assert result.plan.send_as == "vera"
    assert result.plan.selected_facts[-1].path == "payload.window"


def test_ranker_requires_active_offer_for_customer_winback(now):
    store = ContextStore()
    customer = customer_payload(state="lapsed_soft", consent_scopes=["winback_offers"])
    trigger = put_context(
        store,
        trigger_payload(
            kind="customer_lapsed_soft",
            scope="customer",
            customer_id="c-1",
            event_payload={"days_since_last_visit": 45},
        ),
        customer,
    )

    result = DeterministicRanker(ContextResolver(store)).decide(None, "m-1", trigger, now, "c-1")

    assert result.status == DecisionStatus.NO_ACTION
    assert result.no_action_reason == NoActionReason.ACTIVE_OFFER_REQUIRED


def test_ranker_selects_first_deterministic_active_offer(now):
    offers = [
        {"id": "offer-b", "title": "Second", "status": "active"},
        {"id": "offer-a", "title": "First", "status": "active"},
    ]
    merchant = merchant_payload(offers=offers)
    customer = customer_payload(state="lapsed_soft", consent_scopes=["winback_offers"])
    store = ContextStore()
    trigger = put_context(
        store,
        trigger_payload(
            kind="customer_lapsed_soft",
            scope="customer",
            customer_id="c-1",
            event_payload={"days_since_last_visit": 45},
        ),
        customer,
        merchant,
    )

    result = DeterministicRanker(ContextResolver(store)).decide(None, "m-1", trigger, now, "c-1")

    assert result.status == DecisionStatus.SELECTED
    assert result.plan.selected_offer.value["id"] == "offer-a"


def test_rank_method_prefers_higher_score_then_trigger_id():
    store = ContextStore()
    seed_merchant_context(store)
    first_payload = trigger_payload(
        trigger_id="t-a",
        event_payload={"metric": "views", "delta_pct": -10, "window": "7d"},
    )
    second_payload = trigger_payload(
        trigger_id="t-b",
        event_payload={"metric": "views", "delta_pct": -10, "window": "7d"},
    )
    store.put("trigger", "t-a", 1, first_payload)
    store.put("trigger", "t-b", 1, second_payload)
    resolver = ContextResolver(store)
    first_resolved = resolver.resolve(None, "m-1", store.get_trigger("t-a"))
    second_resolved = resolver.resolve(None, "m-1", store.get_trigger("t-b"))
    rule = get_rule("perf_dip")
    fact = Fact(ContextScope.MERCHANT, "m-1", "identity.name", "Mira Dental")
    first = Opportunity(first_resolved, None, rule, (fact,), None, 10, ())
    second = Opportunity(second_resolved, None, rule, (fact,), None, 20, ())

    assert DeterministicRanker(None).rank([first, second]) is second
