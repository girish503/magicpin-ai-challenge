from __future__ import annotations

from enum import Enum


class ContextScope(str, Enum):
    CATEGORY = "category"
    MERCHANT = "merchant"
    CUSTOMER = "customer"
    TRIGGER = "trigger"


class TargetScope(str, Enum):
    MERCHANT = "merchant"
    CUSTOMER = "customer"


class TriggerSource(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class DecisionStatus(str, Enum):
    SELECTED = "selected"
    NO_ACTION = "no_action"


class NoActionReason(str, Enum):
    MISSING_MERCHANT_CONTEXT = "missing_merchant_context"
    MISSING_CATEGORY_CONTEXT = "missing_category_context"
    MISSING_CUSTOMER_CONTEXT = "missing_customer_context"
    TRIGGER_MERCHANT_MISMATCH = "trigger_merchant_mismatch"
    MERCHANT_CUSTOMER_MISMATCH = "merchant_customer_mismatch"
    CATEGORY_MISMATCH = "category_mismatch"
    TRIGGER_SCOPE_INVALID = "trigger_scope_invalid"
    EXPIRED_TRIGGER = "expired_trigger"
    PLACEHOLDER_EVIDENCE = "placeholder_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED_TRIGGER_KIND = "unsupported_trigger_kind"
    CONSENT_REJECTED = "consent_rejected"
    SUPPRESSED = "suppressed"
    CUSTOMER_STATE_INELIGIBLE = "customer_state_ineligible"
    ACTIVE_OFFER_REQUIRED = "active_offer_required"
    CONVERSATION_TERMINAL = "conversation_terminal"
    DUPLICATE_IN_CONVERSATION = "duplicate_in_conversation"
    CONTEXT_VALIDATION_ERROR = "context_validation_error"


class ConsentReason(str, Enum):
    NOT_REQUIRED = "not_required"
    ALLOWED = "allowed"
    MISSING_CUSTOMER = "missing_customer"
    MERCHANT_MISMATCH = "merchant_mismatch"
    OPTED_OUT = "opted_out"
    REMINDER_OPT_OUT = "reminder_opt_out"
    MISSING_CONSENT = "missing_consent"
    MISSING_REQUIRED_SCOPE = "missing_required_scope"
    UNMAPPED_TRIGGER_SCOPE = "unmapped_trigger_scope"


class SuppressionReason(str, Enum):
    ALLOWED = "allowed"
    EXPIRED_TRIGGER = "expired_trigger"
    RECORDED_SUPPRESSION_KEY = "recorded_suppression_key"
    DUPLICATE_IN_CONVERSATION = "duplicate_in_conversation"
    CONVERSATION_TERMINAL = "conversation_terminal"


class ConversationStatus(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    WAITING_FOR_MERCHANT = "waiting_for_merchant"
    ACTION_READY = "action_ready"
    COMPLETED = "completed"
    SUPPRESSED = "suppressed"


class Intent(str, Enum):
    UNKNOWN = "unknown"
    AUTO_REPLY = "auto_reply"
    COMMITMENT = "commitment"
    STOP = "stop"
    DEFER = "defer"
    OFF_TOPIC = "off_topic"


class StoreUpdateStatus(str, Enum):
    INSERTED = "inserted"
    UPDATED = "updated"
    IDEMPOTENT = "idempotent"
    STALE = "stale"
