from __future__ import annotations

from typing import Mapping, Optional, Tuple

from vera.domain.enums import ConsentReason, TargetScope
from vera.domain.models import ConsentDecision, CustomerContext, TriggerContext

# These are exact, fail-closed mappings derived from the explicit names present
# in the supplied dataset. Unknown trigger kinds intentionally receive no grant.
REQUIRED_CONSENT_SCOPE: Mapping[str, Tuple[str, ...]] = {
    "appointment_tomorrow": ("appointment_reminders",),
    "recall_due": ("recall_reminders",),
    "chronic_refill_due": ("refill_reminders",),
    "customer_lapsed_hard": ("winback_offers",),
    "customer_lapsed_soft": ("winback_offers",),
    "trial_followup": ("kids_program_updates",),
    "wedding_package_followup": ("bridal_package_followup",),
}


def evaluate_customer_consent(trigger: TriggerContext, customer: Optional[CustomerContext]) -> ConsentDecision:
    """Return a permission decision without guessing semantic consent equivalence."""
    if trigger.scope == TargetScope.MERCHANT:
        return ConsentDecision(True, ConsentReason.NOT_REQUIRED, rationale="merchant-scoped trigger does not require customer consent")
    if customer is None:
        return ConsentDecision(False, ConsentReason.MISSING_CUSTOMER, rationale="customer-scoped trigger has no customer context")
    if customer.merchant_id != trigger.merchant_id or customer.customer_id != trigger.customer_id:
        return ConsentDecision(False, ConsentReason.MERCHANT_MISMATCH, rationale="customer does not match trigger ownership")

    preferences = customer.payload.get("preferences", {})
    consent = customer.payload.get("consent", {})
    consent_scopes = tuple(str(scope) for scope in consent.get("scope", []) if isinstance(scope, str))
    if preferences.get("opted_out") is True or consent.get("opted_out") is True or "opt_out" in consent_scopes:
        return ConsentDecision(False, ConsentReason.OPTED_OUT, rationale="customer is explicitly opted out")
    if preferences.get("reminder_opt_in") is False:
        return ConsentDecision(False, ConsentReason.REMINDER_OPT_OUT, rationale="customer reminder preference is disabled")
    if not consent.get("opted_in_at") or not consent_scopes:
        return ConsentDecision(False, ConsentReason.MISSING_CONSENT, rationale="customer has no timestamped consent scope")
    required = REQUIRED_CONSENT_SCOPE.get(trigger.kind)
    if required is None:
        return ConsentDecision(False, ConsentReason.UNMAPPED_TRIGGER_SCOPE, rationale=f"no fail-closed consent mapping for {trigger.kind}")
    matched = next((scope for scope in required if scope in consent_scopes), None)
    if matched is None:
        return ConsentDecision(
            False,
            ConsentReason.MISSING_REQUIRED_SCOPE,
            required_scopes=required,
            rationale=f"customer consent lacks required scope(s): {', '.join(required)}",
        )
    return ConsentDecision(
        True,
        ConsentReason.ALLOWED,
        required_scopes=required,
        matched_scope=matched,
        rationale=f"customer consent permits {trigger.kind} through {matched}",
    )
