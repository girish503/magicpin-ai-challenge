from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from vera.context.resolver import ContextResolver
from vera.context.validation import parse_iso8601, value_at_path
from vera.decision.opportunity import OpportunityRule
from vera.decision.trigger_analyzer import TriggerAnalysis, TriggerAnalyzer
from vera.domain.enums import ContextScope, NoActionReason, TargetScope
from vera.domain.models import (
    ContextResolutionError,
    DecisionResult,
    Fact,
    MessagePlan,
    ResolvedContext,
    TriggerContext,
)
from vera.messaging.message_plan import build_message_plan
from vera.policy.consent import evaluate_customer_consent
from vera.policy.suppression import SuppressionRegistry
from vera.domain.models import ConversationState


@dataclass(frozen=True)
class Opportunity:
    resolved: ResolvedContext
    analysis: TriggerAnalysis
    rule: OpportunityRule
    facts: Tuple[Fact, ...]
    selected_offer: Optional[Fact]
    score: int
    score_components: Tuple[Tuple[str, str], ...]


class DeterministicRanker:
    """Pure, explainable decision engine over current supplied context."""

    def __init__(self, resolver: ContextResolver, suppression: SuppressionRegistry | None = None) -> None:
        self.resolver = resolver
        self.suppression = suppression or SuppressionRegistry()
        self.analyzer = TriggerAnalyzer()

    def decide(
        self,
        category_id: Optional[str],
        merchant_id: str,
        trigger: TriggerContext | str,
        now: datetime,
        customer_id: Optional[str] = None,
        conversation: Optional[ConversationState] = None,
    ) -> DecisionResult:
        try:
            resolved = self.resolver.resolve(category_id, merchant_id, trigger, customer_id)
        except ContextResolutionError as exc:
            return DecisionResult.no_action(exc.reason, str(exc))
        analysis = self.analyzer.analyze(resolved, now)
        if not analysis.actionable:
            assert analysis.no_action_reason is not None
            return DecisionResult.no_action(analysis.no_action_reason, analysis.rationale)
        if resolved.customer is not None:
            consent = evaluate_customer_consent(resolved.trigger, resolved.customer)
            if not consent.allowed:
                return DecisionResult.no_action(NoActionReason.CONSENT_REJECTED, consent.rationale)
        suppression = self.suppression.evaluate(
            resolved.trigger,
            resolved.merchant.merchant_id,
            resolved.customer.customer_id if resolved.customer else None,
            now,
            conversation,
        )
        if not suppression.allowed:
            reason = {
                "expired_trigger": NoActionReason.EXPIRED_TRIGGER,
                "conversation_terminal": NoActionReason.CONVERSATION_TERMINAL,
                "duplicate_in_conversation": NoActionReason.DUPLICATE_IN_CONVERSATION,
            }.get(suppression.reason.value, NoActionReason.SUPPRESSED)
            return DecisionResult.no_action(reason, suppression.rationale)
        opportunity_or_result = self._build_opportunity(resolved, analysis, now)
        if isinstance(opportunity_or_result, DecisionResult):
            return opportunity_or_result
        plan = build_message_plan(
            opportunity_or_result.resolved,
            opportunity_or_result.rule,
            opportunity_or_result.facts,
            opportunity_or_result.selected_offer,
            opportunity_or_result.score,
            opportunity_or_result.score_components,
        )
        return DecisionResult.selected(plan, opportunity_or_result.score)

    def rank(self, opportunities: Iterable[Opportunity]) -> Optional[Opportunity]:
        """Choose the strongest plan deterministically; ID resolves score ties."""
        ranked = sorted(opportunities, key=lambda item: (-item.score, item.resolved.trigger.trigger_id))
        return ranked[0] if ranked else None

    def commit_selected(self, result: DecisionResult, now: datetime) -> None:
        """Record suppression only after a caller actually commits the selected action."""
        if result.plan is None:
            return
        trigger = self.resolver.store.get_trigger(result.plan.trigger_id)
        if trigger is None:
            return
        self.suppression.mark_sent(trigger, result.plan.merchant_id, result.plan.customer_id, now)

    def _build_opportunity(self, resolved: ResolvedContext, analysis: TriggerAnalysis, now: datetime) -> Opportunity | DecisionResult:
        rule = analysis.rule
        if rule is None:
            return DecisionResult.no_action(NoActionReason.UNSUPPORTED_TRIGGER_KIND, "no opportunity rule exists")
        if rule.requires_customer and resolved.customer is None:
            return DecisionResult.no_action(NoActionReason.MISSING_CUSTOMER_CONTEXT, "opportunity requires a customer context")
        if resolved.customer is not None and rule.customer_states:
            state = resolved.customer.payload.get("state")
            if state not in rule.customer_states:
                return DecisionResult.no_action(NoActionReason.CUSTOMER_STATE_INELIGIBLE, f"customer state {state!r} is not eligible for {rule.kind}")
        selected_offer = self._select_active_offer(resolved) if rule.requires_active_offer else None
        if rule.requires_active_offer and selected_offer is None:
            return DecisionResult.no_action(NoActionReason.ACTIVE_OFFER_REQUIRED, f"{rule.kind} requires a real active merchant offer")
        facts = self._select_facts(resolved, rule, selected_offer)
        score, components = self._score(resolved, analysis, rule, selected_offer, now)
        return Opportunity(resolved, analysis, rule, facts, selected_offer, score, components)

    @staticmethod
    def _select_active_offer(resolved: ResolvedContext) -> Optional[Fact]:
        raw_offers = resolved.merchant.payload.get("offers", [])
        active = [offer for offer in raw_offers if isinstance(offer, Mapping) and offer.get("status") == "active" and offer.get("title")]
        if not active:
            return None
        offer = sorted(active, key=lambda item: (str(item.get("id", "")), str(item.get("title", ""))))[0]
        offer_id = str(offer.get("id", offer.get("title")))
        return Fact(ContextScope.MERCHANT, resolved.merchant.merchant_id, f"offers[id={offer_id}]", dict(offer))

    @staticmethod
    def _select_facts(resolved: ResolvedContext, rule: OpportunityRule, selected_offer: Optional[Fact]) -> Tuple[Fact, ...]:
        facts: list[Fact] = []
        merchant_identity = resolved.merchant.payload.get("identity", {})
        if merchant_identity.get("name"):
            facts.append(Fact(ContextScope.MERCHANT, resolved.merchant.merchant_id, "identity.name", merchant_identity["name"]))
        if merchant_identity.get("owner_first_name"):
            facts.append(Fact(ContextScope.MERCHANT, resolved.merchant.merchant_id, "identity.owner_first_name", merchant_identity["owner_first_name"]))
        for path in rule.required_all:
            facts.append(Fact(ContextScope.TRIGGER, resolved.trigger.trigger_id, f"payload.{path}", value_at_path(resolved.trigger.event_payload, path)))
        digest_id = resolved.trigger.event_payload.get("top_item_id") or resolved.trigger.event_payload.get("digest_item_id") or resolved.trigger.event_payload.get("alert_id")
        if isinstance(digest_id, str):
            for item in resolved.category.payload.get("digest", []):
                if isinstance(item, Mapping) and item.get("id") == digest_id:
                    for field in ("title", "source", "summary", "actionable"):
                        if item.get(field) is not None:
                            facts.append(Fact(ContextScope.CATEGORY, resolved.category.slug, f"digest[id={digest_id}].{field}", item[field]))
                    break
        if resolved.customer is not None:
            identity = resolved.customer.payload.get("identity", {})
            if identity.get("name"):
                facts.append(Fact(ContextScope.CUSTOMER, resolved.customer.customer_id, "identity.name", identity["name"]))
            if identity.get("language_pref"):
                facts.append(Fact(ContextScope.CUSTOMER, resolved.customer.customer_id, "identity.language_pref", identity["language_pref"]))
            facts.append(Fact(ContextScope.CUSTOMER, resolved.customer.customer_id, "state", resolved.customer.payload.get("state")))
        if selected_offer is not None:
            facts.append(selected_offer)
        return tuple(facts)

    @staticmethod
    def _score(
        resolved: ResolvedContext,
        analysis: TriggerAnalysis,
        rule: OpportunityRule,
        selected_offer: Optional[Fact],
        now: datetime,
    ) -> tuple[int, Tuple[Tuple[str, str], ...]]:
        components: list[Tuple[str, str]] = []
        priority = rule.priority * 100
        components.append(("rule_priority", str(priority)))
        urgency = analysis.urgency * 10
        components.append(("trigger_urgency", str(urgency)))
        evidence = len(analysis.evidence_fields) * 3
        components.append(("evidence_strength", str(evidence)))
        category_fit = 2 if resolved.trigger.event_payload.get("category") in {None, resolved.category.slug} else 0
        components.append(("category_relevance", str(category_fit)))
        history = resolved.merchant.payload.get("conversation_history", [])
        history_component = min(len(history), 3) if isinstance(history, Sequence) else 0
        components.append(("conversation_history", str(history_component)))
        customer_component = 2 if resolved.customer is not None else 0
        components.append(("customer_context", str(customer_component)))
        offer_component = 1 if selected_offer is not None else 0
        components.append(("active_offer", str(offer_component)))
        hours_to_expiry = max(0.0, (parse_iso8601(resolved.trigger.expires_at) - now).total_seconds() / 3600)
        recency = 3 if hours_to_expiry <= 24 else 2 if hours_to_expiry <= 168 else 1
        components.append(("recency", str(recency)))
        return priority + urgency + evidence + category_fit + history_component + customer_component + offer_component + recency, tuple(components)
