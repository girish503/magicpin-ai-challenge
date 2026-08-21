import pytest

from conftest import (
    category_payload,
    customer_payload,
    merchant_payload,
    seed_customer_context,
    seed_merchant_context,
    trigger_payload,
)
from vera.context.resolver import ContextResolver
from vera.domain.enums import NoActionReason
from vera.domain.models import ContextResolutionError


def put_trigger(store, payload):
    store.put("trigger", payload["id"], 1, payload)
    return store.get_trigger(payload["id"])


def test_resolver_resolves_merchant_trigger(seeded_store):
    trigger = put_trigger(seeded_store, trigger_payload(event_payload={"metric": "views", "delta_pct": -10, "window": "7d"}))

    resolved = ContextResolver(seeded_store).resolve(None, "m-1", trigger)

    assert resolved.merchant.merchant_id == "m-1"
    assert resolved.customer is None


def test_resolver_resolves_owned_customer_trigger(seeded_store):
    customer = customer_payload(consent_scopes=["appointment_reminders"])
    seed_customer_context(seeded_store, customer)
    payload = trigger_payload(
        kind="appointment_tomorrow",
        scope="customer",
        customer_id="c-1",
        event_payload={"available_slots": ["10:00"]},
    )
    trigger = put_trigger(seeded_store, payload)

    resolved = ContextResolver(seeded_store).resolve(None, "m-1", trigger, "c-1")

    assert resolved.customer.customer_id == "c-1"


def test_resolver_rejects_trigger_merchant_mismatch(seeded_store):
    trigger = put_trigger(seeded_store, trigger_payload(merchant_id="other"))

    with pytest.raises(ContextResolutionError) as error:
        ContextResolver(seeded_store).resolve(None, "m-1", trigger)

    assert error.value.reason == NoActionReason.TRIGGER_MERCHANT_MISMATCH


def test_resolver_rejects_customer_from_another_merchant(seeded_store):
    customer = customer_payload(merchant_id="other", consent_scopes=["appointment_reminders"])
    seed_customer_context(seeded_store, customer)
    payload = trigger_payload(
        kind="appointment_tomorrow",
        scope="customer",
        customer_id="c-1",
        event_payload={"available_slots": ["10:00"]},
    )
    trigger = put_trigger(seeded_store, payload)

    with pytest.raises(ContextResolutionError) as error:
        ContextResolver(seeded_store).resolve(None, "m-1", trigger)

    assert error.value.reason == NoActionReason.MERCHANT_CUSTOMER_MISMATCH


def test_resolver_rejects_requested_category_mismatch(seeded_store):
    trigger = put_trigger(seeded_store, trigger_payload())

    with pytest.raises(ContextResolutionError) as error:
        ContextResolver(seeded_store).resolve("gyms", "m-1", trigger)

    assert error.value.reason == NoActionReason.CATEGORY_MISMATCH
