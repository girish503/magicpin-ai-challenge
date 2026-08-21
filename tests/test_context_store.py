import pytest

from conftest import category_payload, merchant_payload
from vera.context.store import ContextStore
from vera.domain.enums import ContextScope, StoreUpdateStatus
from vera.domain.models import ContextValidationError


def test_store_inserts_and_counts_contexts():
    store = ContextStore()
    result = store.put("category", "dentists", 1, category_payload())

    assert result.accepted
    assert result.status == StoreUpdateStatus.INSERTED
    assert store.counts()[ContextScope.CATEGORY.value] == 1
    assert store.get_category("dentists").version == 1


def test_store_same_version_is_idempotent_and_keeps_original_payload():
    store = ContextStore()
    store.put("merchant", "m-1", 1, merchant_payload())
    result = store.put("merchant", "m-1", 1, {**merchant_payload(), "category_slug": "gyms"})

    assert result.status == StoreUpdateStatus.IDEMPOTENT
    assert store.get_merchant("m-1").category_slug == "dentists"


def test_store_higher_version_replaces_and_lower_version_is_stale():
    store = ContextStore()
    store.put("merchant", "m-1", 1, merchant_payload())
    updated = store.put("merchant", "m-1", 2, {**merchant_payload(), "category_slug": "gyms"})
    stale = store.put("merchant", "m-1", 1, merchant_payload())

    assert updated.status == StoreUpdateStatus.UPDATED
    assert store.get_merchant("m-1").version == 2
    assert store.get_merchant("m-1").category_slug == "gyms"
    assert stale.status == StoreUpdateStatus.STALE
    assert stale.current_version == 2


def test_store_rejects_invalid_payload_without_storing_it():
    store = ContextStore()

    with pytest.raises(ContextValidationError):
        store.put("merchant", "m-1", 1, {"merchant_id": "m-1"})

    assert store.get_merchant("m-1") is None
