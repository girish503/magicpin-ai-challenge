from __future__ import annotations

from typing import Optional

from vera.context.store import ContextStore
from vera.domain.enums import NoActionReason, TargetScope
from vera.domain.models import ContextResolutionError, ResolvedContext, TriggerContext


class ContextResolver:
    def __init__(self, store: ContextStore) -> None:
        self.store = store

    def resolve(
        self,
        category_id: Optional[str],
        merchant_id: str,
        trigger: TriggerContext | str,
        customer_id: Optional[str] = None,
    ) -> ResolvedContext:
        trigger_context = self.store.get_trigger(trigger) if isinstance(trigger, str) else trigger
        if trigger_context is None:
            raise ContextResolutionError(NoActionReason.CONTEXT_VALIDATION_ERROR, "trigger context is unavailable")
        merchant = self.store.get_merchant(merchant_id)
        if merchant is None:
            raise ContextResolutionError(NoActionReason.MISSING_MERCHANT_CONTEXT, "merchant context is unavailable")
        if trigger_context.merchant_id != merchant.merchant_id:
            raise ContextResolutionError(NoActionReason.TRIGGER_MERCHANT_MISMATCH, "trigger merchant_id does not match requested merchant")
        payload_category = trigger_context.event_payload.get("category")
        if payload_category is not None and payload_category != merchant.category_slug:
            raise ContextResolutionError(NoActionReason.CATEGORY_MISMATCH, "trigger category does not match merchant category")
        if category_id is not None and category_id != merchant.category_slug:
            raise ContextResolutionError(NoActionReason.CATEGORY_MISMATCH, "requested category does not match merchant category")
        category = self.store.get_category(merchant.category_slug)
        if category is None:
            raise ContextResolutionError(NoActionReason.MISSING_CATEGORY_CONTEXT, "category context is unavailable")
        if trigger_context.scope == TargetScope.MERCHANT:
            if customer_id is not None:
                raise ContextResolutionError(NoActionReason.TRIGGER_SCOPE_INVALID, "merchant trigger cannot resolve a customer")
            return ResolvedContext(category=category, merchant=merchant, trigger=trigger_context)
        expected_customer_id = trigger_context.customer_id
        if expected_customer_id is None:
            raise ContextResolutionError(NoActionReason.MISSING_CUSTOMER_CONTEXT, "customer trigger has no customer_id")
        if customer_id is not None and customer_id != expected_customer_id:
            raise ContextResolutionError(NoActionReason.MERCHANT_CUSTOMER_MISMATCH, "requested customer does not match trigger customer")
        customer = self.store.get_customer(expected_customer_id)
        if customer is None:
            raise ContextResolutionError(NoActionReason.MISSING_CUSTOMER_CONTEXT, "customer context is unavailable")
        if customer.merchant_id != merchant.merchant_id:
            raise ContextResolutionError(NoActionReason.MERCHANT_CUSTOMER_MISMATCH, "customer does not belong to merchant")
        return ResolvedContext(category=category, merchant=merchant, trigger=trigger_context, customer=customer)
