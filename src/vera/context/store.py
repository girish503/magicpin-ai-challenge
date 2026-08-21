from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from vera.domain.enums import ContextScope, StoreUpdateStatus
from vera.domain.models import (
    CategoryContext,
    ContextValidationError,
    CustomerContext,
    MerchantContext,
    StoreUpdateResult,
    TriggerContext,
)

StoredContext = Union[CategoryContext, MerchantContext, CustomerContext, TriggerContext]


@dataclass(frozen=True)
class ContextRecord:
    context: StoredContext
    delivered_at: Optional[str]


class ContextStore:
    """In-memory versioned store matching the future `/v1/context` semantics."""

    def __init__(self) -> None:
        self._records: Dict[Tuple[ContextScope, str], ContextRecord] = {}

    def put(
        self,
        scope: ContextScope | str,
        context_id: str,
        version: int,
        payload: Mapping[str, Any],
        delivered_at: Optional[str] = None,
    ) -> StoreUpdateResult:
        normalized_scope = ContextScope(scope)
        context = self._parse(normalized_scope, context_id, version, payload)
        key = (normalized_scope, context_id)
        current = self._records.get(key)
        if current is not None:
            if version == current.context.version:
                return StoreUpdateResult(StoreUpdateStatus.IDEMPOTENT, normalized_scope, context_id, current.context.version)
            if version < current.context.version:
                return StoreUpdateResult(StoreUpdateStatus.STALE, normalized_scope, context_id, current.context.version)
            status = StoreUpdateStatus.UPDATED
        else:
            status = StoreUpdateStatus.INSERTED
        self._records[key] = ContextRecord(context=context, delivered_at=delivered_at)
        return StoreUpdateResult(status, normalized_scope, context_id, version)

    def get(self, scope: ContextScope | str, context_id: str) -> Optional[StoredContext]:
        record = self._records.get((ContextScope(scope), context_id))
        return record.context if record else None

    def get_category(self, context_id: str) -> Optional[CategoryContext]:
        value = self.get(ContextScope.CATEGORY, context_id)
        return value if isinstance(value, CategoryContext) else None

    def get_merchant(self, context_id: str) -> Optional[MerchantContext]:
        value = self.get(ContextScope.MERCHANT, context_id)
        return value if isinstance(value, MerchantContext) else None

    def get_customer(self, context_id: str) -> Optional[CustomerContext]:
        value = self.get(ContextScope.CUSTOMER, context_id)
        return value if isinstance(value, CustomerContext) else None

    def get_trigger(self, context_id: str) -> Optional[TriggerContext]:
        value = self.get(ContextScope.TRIGGER, context_id)
        return value if isinstance(value, TriggerContext) else None

    def counts(self) -> Dict[str, int]:
        return {scope.value: sum(1 for stored_scope, _ in self._records if stored_scope == scope) for scope in ContextScope}

    def record(self, scope: ContextScope | str, context_id: str) -> Optional[ContextRecord]:
        return self._records.get((ContextScope(scope), context_id))

    @staticmethod
    def _parse(scope: ContextScope, context_id: str, version: int, payload: Mapping[str, Any]) -> StoredContext:
        if not isinstance(context_id, str) or not context_id:
            raise ContextValidationError("context_id must be a non-empty string")
        factories = {
            ContextScope.CATEGORY: CategoryContext.from_payload,
            ContextScope.MERCHANT: MerchantContext.from_payload,
            ContextScope.CUSTOMER: CustomerContext.from_payload,
            ContextScope.TRIGGER: TriggerContext.from_payload,
        }
        return factories[scope](context_id, version, payload)
