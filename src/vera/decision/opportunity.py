from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple

from vera.domain.enums import TargetScope


@dataclass(frozen=True)
class OpportunityRule:
    kind: str
    scope: TargetScope
    priority: int
    strategy: str
    hook_type: str
    cta_strategy: str
    required_all: Tuple[str, ...]
    required_any: Tuple[str, ...] = ()
    requires_customer: bool = False
    requires_active_offer: bool = False
    customer_states: FrozenSet[str] = frozenset()


def _merchant(kind: str, priority: int, strategy: str, hook: str, cta: str, *evidence: str) -> OpportunityRule:
    return OpportunityRule(kind, TargetScope.MERCHANT, priority, strategy, hook, cta, evidence)


def _customer(
    kind: str,
    priority: int,
    strategy: str,
    hook: str,
    cta: str,
    *evidence: str,
    requires_active_offer: bool = False,
    customer_states: FrozenSet[str] = frozenset(),
) -> OpportunityRule:
    return OpportunityRule(
        kind,
        TargetScope.CUSTOMER,
        priority,
        strategy,
        hook,
        cta,
        evidence,
        requires_customer=True,
        requires_active_offer=requires_active_offer,
        customer_states=customer_states,
    )


# Every known dataset kind has a rule. Required fields are factual gates, not
# templates: a rule never creates a fact that the payload did not supply.
OPPORTUNITY_RULES: Dict[str, OpportunityRule] = {
    "active_planning_intent": _merchant("active_planning_intent", 5, "execution_plan", "intent_handoff", "binary_confirm", "intent_topic", "merchant_last_message"),
    "category_seasonal": _merchant("category_seasonal", 2, "seasonal_operations", "seasonal_signal", "open_ended", "season", "trends"),
    "cde_opportunity": _merchant("cde_opportunity", 2, "professional_development", "knowledge_opportunity", "open_ended", "digest_item_id"),
    "competitor_opened": _merchant("competitor_opened", 3, "competitive_response", "local_competition", "open_ended", "competitor_name", "distance_km"),
    "curious_ask_due": _merchant("curious_ask_due", 1, "curiosity_prompt", "merchant_question", "open_ended", "ask_template"),
    "dormant_with_vera": _merchant("dormant_with_vera", 2, "reengagement", "relationship_reopen", "binary_yes_no", "days_since_last_merchant_message"),
    "festival_upcoming": _merchant("festival_upcoming", 2, "seasonal_campaign", "event_window", "open_ended", "festival", "date"),
    "gbp_unverified": _merchant("gbp_unverified", 4, "profile_verification", "profile_health", "binary_yes_no", "verified", "verification_path"),
    "ipl_match_today": _merchant("ipl_match_today", 3, "event_operations", "local_event", "open_ended", "match", "match_time_iso", "is_weeknight"),
    "milestone_reached": _merchant("milestone_reached", 2, "milestone_follow_on", "celebration", "open_ended", "metric", "milestone_value", "value_now"),
    "perf_dip": _merchant("perf_dip", 4, "performance_recovery", "diagnostic", "open_ended", "metric", "delta_pct", "window"),
    "perf_spike": _merchant("perf_spike", 2, "performance_expansion", "reinforcement", "open_ended", "metric", "delta_pct", "window"),
    "regulation_change": _merchant("regulation_change", 5, "compliance_alert", "compliance_deadline", "binary_yes_no", "top_item_id", "deadline_iso"),
    "renewal_due": _merchant("renewal_due", 5, "subscription_renewal", "time_bound_renewal", "binary_confirm", "days_remaining", "plan", "renewal_amount"),
    "research_digest": _merchant("research_digest", 2, "knowledge_digest", "source_citation", "open_ended", "top_item_id"),
    "review_theme_emerged": _merchant("review_theme_emerged", 4, "review_response", "customer_feedback", "open_ended", "theme", "occurrences_30d"),
    "seasonal_perf_dip": _merchant("seasonal_perf_dip", 3, "seasonal_reframe", "benchmark_reframe", "open_ended", "metric", "delta_pct", "is_expected_seasonal"),
    "supply_alert": _merchant("supply_alert", 5, "supply_compliance", "safety_alert", "binary_yes_no", "alert_id", "affected_batches", "molecule"),
    "winback_eligible": _merchant("winback_eligible", 4, "merchant_winback", "loss_aversion", "binary_yes_no", "days_since_expiry", "lapsed_customers_added_since_expiry"),
    "appointment_tomorrow": _customer("appointment_tomorrow", 4, "appointment_reminder", "appointment_time", "binary_confirm", "available_slots", customer_states=frozenset({"new", "active", "lapsed_soft"})),
    "chronic_refill_due": _customer("chronic_refill_due", 5, "refill_reminder", "refill_due", "binary_confirm", "molecule_list", "stock_runs_out_iso", customer_states=frozenset({"active", "lapsed_soft"})),
    "customer_lapsed_hard": _customer("customer_lapsed_hard", 3, "winback", "no_shame_return", "binary_yes_no", "days_since_last_visit", requires_active_offer=True, customer_states=frozenset({"lapsed_hard", "churned"})),
    "customer_lapsed_soft": _customer("customer_lapsed_soft", 3, "winback", "gentle_recall", "binary_yes_no", "days_since_last_visit", requires_active_offer=True, customer_states=frozenset({"lapsed_soft"})),
    "recall_due": _customer("recall_due", 4, "recall_reminder", "due_service", "multi_choice_slot", "service_due", "due_date", "available_slots", customer_states=frozenset({"active", "lapsed_soft"})),
    "trial_followup": _customer("trial_followup", 3, "trial_conversion", "next_session", "multi_choice_slot", "trial_date", "next_session_options", customer_states=frozenset({"new", "active"})),
    "wedding_package_followup": _customer("wedding_package_followup", 4, "bridal_followup", "event_countdown", "binary_yes_no", "wedding_date", "next_step_window_open", requires_active_offer=True, customer_states=frozenset({"new", "active"})),
}


def get_rule(kind: str) -> OpportunityRule | None:
    return OPPORTUNITY_RULES.get(kind)
