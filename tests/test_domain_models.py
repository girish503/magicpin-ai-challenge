import pytest

from conftest import category_payload, customer_payload, merchant_payload, trigger_payload
from vera.domain.enums import TargetScope
from vera.domain.models import (
    CategoryContext,
    ContextValidationError,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)


def test_context_factories_build_typed_contexts():
    category = CategoryContext.from_payload("dentists", 1, category_payload())
    merchant = MerchantContext.from_payload("m-1", 1, merchant_payload())
    customer = CustomerContext.from_payload("c-1", 1, customer_payload())
    trigger = TriggerContext.from_payload("t-1", 1, trigger_payload())

    assert category.slug == "dentists"
    assert merchant.category_slug == "dentists"
    assert customer.merchant_id == "m-1"
    assert trigger.scope == TargetScope.MERCHANT
    assert trigger.customer_id is None


def test_context_factory_rejects_non_positive_version():
    with pytest.raises(ContextValidationError, match="positive integer"):
        CategoryContext.from_payload("dentists", 0, category_payload())


def test_context_factory_rejects_identity_mismatch():
    with pytest.raises(ContextValidationError, match="context_id"):
        MerchantContext.from_payload("other", 1, merchant_payload())


def test_customer_trigger_requires_customer_id():
    payload = trigger_payload(scope="customer", customer_id=None)

    with pytest.raises(ContextValidationError, match="requires customer_id"):
        TriggerContext.from_payload("t-1", 1, payload)


def test_merchant_trigger_rejects_customer_id():
    payload = trigger_payload(scope="merchant", customer_id="c-1")

    with pytest.raises(ContextValidationError, match="must be null"):
        TriggerContext.from_payload("t-1", 1, payload)
