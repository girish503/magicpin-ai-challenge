import sys
from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


NOW = datetime.fromisoformat("2026-04-26T10:00:00+00:00")


def category_payload(slug="dentists"):
    return {"slug": slug, "voice": {"tone": "respectful"}, "digest": []}


def merchant_payload(merchant_id="m-1", category_slug="dentists", offers=None):
    return {
        "merchant_id": merchant_id,
        "category_slug": category_slug,
        "identity": {
            "name": "Mira Dental",
            "owner_first_name": "Mira",
            "languages": ["en", "hi"],
        },
        "offers": [] if offers is None else offers,
        "conversation_history": [],
    }


def customer_payload(
    customer_id="c-1",
    merchant_id="m-1",
    state="active",
    consent_scopes=None,
    reminder_opt_in=True,
):
    return {
        "customer_id": customer_id,
        "merchant_id": merchant_id,
        "identity": {"name": "Asha", "language_pref": "en"},
        "state": state,
        "preferences": {"reminder_opt_in": reminder_opt_in},
        "consent": {
            "opted_in_at": "2026-04-01T09:00:00Z",
            "scope": [] if consent_scopes is None else consent_scopes,
        },
    }


def trigger_payload(
    trigger_id="t-1",
    kind="perf_dip",
    scope="merchant",
    merchant_id="m-1",
    customer_id=None,
    event_payload=None,
    expires_at="2026-04-27T10:00:00Z",
    urgency=3,
):
    return {
        "id": trigger_id,
        "scope": scope,
        "kind": kind,
        "source": "internal",
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "payload": {} if event_payload is None else event_payload,
        "urgency": urgency,
        "suppression_key": f"suppression-{trigger_id}",
        "expires_at": expires_at,
    }


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def store():
    from vera.context.store import ContextStore

    return ContextStore()


def seed_merchant_context(store, merchant=None, category=None, version=1):
    merchant = merchant or merchant_payload()
    category = category or category_payload(merchant["category_slug"])
    store.put("category", category["slug"], version, category)
    store.put("merchant", merchant["merchant_id"], version, merchant)


def seed_customer_context(store, customer=None, version=1):
    customer = customer or customer_payload()
    store.put("customer", customer["customer_id"], version, customer)


@pytest.fixture
def seeded_store(store):
    seed_merchant_context(store)
    return store
