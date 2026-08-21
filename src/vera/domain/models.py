from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from vera.domain.enums import (
    ConsentReason,
    ContextScope,
    ConversationStatus,
    DecisionStatus,
    Intent,
    NoActionReason,
    StoreUpdateStatus,
    SuppressionReason,
    TargetScope,
    TriggerSource,
)


class ContextValidationError(ValueError):
    """Raised when a context payload cannot safely be stored."""


class ContextResolutionError(ValueError):
    """Raised when independently valid contexts cannot be used together."""

    def __init__(self, reason: NoActionReason, message: str):
        super().__init__(message)
        self.reason = reason


def _required_str(payload: Mapping[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContextValidationError(f"{label}.{key} must be a non-empty string")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContextValidationError(f"{label} must be an object")
    return value


@dataclass(frozen=True)
class CategoryContext:
    context_id: str
    version: int
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, context_id: str, version: int, payload: Mapping[str, Any]) -> "CategoryContext":
        _validate_version(version)
        payload = _mapping(payload, "category payload")
        slug = _required_str(payload, "slug", "category payload")
        if slug != context_id:
            raise ContextValidationError("category context_id must match payload.slug")
        _mapping(payload.get("voice"), "category payload.voice")
        return cls(context_id=context_id, version=version, payload=payload)

    @property
    def slug(self) -> str:
        return self.context_id


@dataclass(frozen=True)
class MerchantContext:
    context_id: str
    version: int
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, context_id: str, version: int, payload: Mapping[str, Any]) -> "MerchantContext":
        _validate_version(version)
        payload = _mapping(payload, "merchant payload")
        merchant_id = _required_str(payload, "merchant_id", "merchant payload")
        if merchant_id != context_id:
            raise ContextValidationError("merchant context_id must match payload.merchant_id")
        _required_str(payload, "category_slug", "merchant payload")
        _mapping(payload.get("identity"), "merchant payload.identity")
        return cls(context_id=context_id, version=version, payload=payload)

    @property
    def merchant_id(self) -> str:
        return self.context_id

    @property
    def category_slug(self) -> str:
        return str(self.payload["category_slug"])


@dataclass(frozen=True)
class CustomerContext:
    context_id: str
    version: int
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, context_id: str, version: int, payload: Mapping[str, Any]) -> "CustomerContext":
        _validate_version(version)
        payload = _mapping(payload, "customer payload")
        customer_id = _required_str(payload, "customer_id", "customer payload")
        if customer_id != context_id:
            raise ContextValidationError("customer context_id must match payload.customer_id")
        _required_str(payload, "merchant_id", "customer payload")
        _mapping(payload.get("identity"), "customer payload.identity")
        _mapping(payload.get("preferences"), "customer payload.preferences")
        _mapping(payload.get("consent"), "customer payload.consent")
        return cls(context_id=context_id, version=version, payload=payload)

    @property
    def customer_id(self) -> str:
        return self.context_id

    @property
    def merchant_id(self) -> str:
        return str(self.payload["merchant_id"])


@dataclass(frozen=True)
class TriggerContext:
    context_id: str
    version: int
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, context_id: str, version: int, payload: Mapping[str, Any]) -> "TriggerContext":
        _validate_version(version)
        payload = _mapping(payload, "trigger payload")
        trigger_id = _required_str(payload, "id", "trigger payload")
        if trigger_id != context_id:
            raise ContextValidationError("trigger context_id must match payload.id")
        scope = _required_str(payload, "scope", "trigger payload")
        if scope not in {item.value for item in TargetScope}:
            raise ContextValidationError("trigger payload.scope must be merchant or customer")
        source = _required_str(payload, "source", "trigger payload")
        if source not in {item.value for item in TriggerSource}:
            raise ContextValidationError("trigger payload.source must be internal or external")
        _required_str(payload, "kind", "trigger payload")
        _required_str(payload, "merchant_id", "trigger payload")
        _required_str(payload, "suppression_key", "trigger payload")
        _required_str(payload, "expires_at", "trigger payload")
        _mapping(payload.get("payload"), "trigger payload.payload")
        urgency = payload.get("urgency")
        if not isinstance(urgency, int) or not 1 <= urgency <= 5:
            raise ContextValidationError("trigger payload.urgency must be an integer from 1 to 5")
        customer_id = payload.get("customer_id")
        if scope == TargetScope.CUSTOMER.value and (not isinstance(customer_id, str) or not customer_id):
            raise ContextValidationError("customer-scoped trigger requires customer_id")
        if scope == TargetScope.MERCHANT.value and customer_id is not None:
            raise ContextValidationError("merchant-scoped trigger customer_id must be null")
        return cls(context_id=context_id, version=version, payload=payload)

    @property
    def trigger_id(self) -> str:
        return self.context_id

    @property
    def scope(self) -> TargetScope:
        return TargetScope(str(self.payload["scope"]))

    @property
    def source(self) -> TriggerSource:
        return TriggerSource(str(self.payload["source"]))

    @property
    def kind(self) -> str:
        return str(self.payload["kind"])

    @property
    def merchant_id(self) -> str:
        return str(self.payload["merchant_id"])

    @property
    def customer_id(self) -> Optional[str]:
        value = self.payload.get("customer_id")
        return str(value) if value is not None else None

    @property
    def event_payload(self) -> Mapping[str, Any]:
        return _mapping(self.payload["payload"], "trigger payload.payload")

    @property
    def urgency(self) -> int:
        return int(self.payload["urgency"])

    @property
    def suppression_key(self) -> str:
        return str(self.payload["suppression_key"])

    @property
    def expires_at(self) -> str:
        return str(self.payload["expires_at"])


@dataclass(frozen=True)
class Fact:
    """A selected fact with a direct path to its supplied source context."""

    source_scope: ContextScope
    source_context_id: str
    path: str
    value: Any


@dataclass(frozen=True)
class ResolvedContext:
    category: CategoryContext
    merchant: MerchantContext
    trigger: TriggerContext
    customer: Optional[CustomerContext] = None


@dataclass(frozen=True)
class ConsentDecision:
    allowed: bool
    reason: ConsentReason
    required_scopes: Tuple[str, ...] = ()
    matched_scope: Optional[str] = None
    rationale: str = ""


@dataclass(frozen=True)
class SuppressionDecision:
    allowed: bool
    reason: SuppressionReason
    rationale: str


@dataclass(frozen=True)
class MessagePlan:
    """Structured instructions for a future composer; it never contains a body."""

    should_send: bool
    target_scope: TargetScope
    trigger_id: str
    trigger_kind: str
    merchant_id: str
    customer_id: Optional[str]
    selected_facts: Tuple[Fact, ...]
    selected_offer: Optional[Fact]
    hook_type: str
    strategy: str
    cta_strategy: str
    send_as: str
    suppression_key: str
    rationale: str
    decision_metadata: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DecisionResult:
    status: DecisionStatus
    rationale: str
    plan: Optional[MessagePlan] = None
    no_action_reason: Optional[NoActionReason] = None
    score: Optional[int] = None

    @classmethod
    def no_action(cls, reason: NoActionReason, rationale: str) -> "DecisionResult":
        return cls(status=DecisionStatus.NO_ACTION, no_action_reason=reason, rationale=rationale)

    @classmethod
    def selected(cls, plan: MessagePlan, score: int) -> "DecisionResult":
        return cls(status=DecisionStatus.SELECTED, plan=plan, rationale=plan.rationale, score=score)


@dataclass(frozen=True)
class StoreUpdateResult:
    status: StoreUpdateStatus
    context_scope: ContextScope
    context_id: str
    current_version: int

    @property
    def accepted(self) -> bool:
        return self.status in {StoreUpdateStatus.INSERTED, StoreUpdateStatus.UPDATED}


@dataclass(frozen=True)
class ConversationMessage:
    from_role: str
    body: str
    at: str
    turn_number: int


@dataclass(frozen=True)
class ConversationState:
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str]
    status: ConversationStatus = ConversationStatus.NEW
    messages: Tuple[ConversationMessage, ...] = ()
    last_sent_action: Optional[str] = None
    last_trigger_id: Optional[str] = None
    sent_trigger_ids: Tuple[str, ...] = ()
    merchant_signals: Tuple[str, ...] = ()
    current_intent: Intent = Intent.UNKNOWN
    pending_action: Optional[str] = None
    updated_at: Optional[str] = None


def _validate_version(version: int) -> None:
    if not isinstance(version, int) or version < 1:
        raise ContextValidationError("context version must be a positive integer")
