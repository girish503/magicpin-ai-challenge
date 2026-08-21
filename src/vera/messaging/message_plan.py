from __future__ import annotations

from typing import Iterable, Optional, Tuple

from vera.decision.opportunity import OpportunityRule
from vera.domain.models import Fact, MessagePlan, ResolvedContext


def build_message_plan(
    resolved: ResolvedContext,
    rule: OpportunityRule,
    facts: Iterable[Fact],
    selected_offer: Optional[Fact],
    score: int,
    score_components: Tuple[Tuple[str, str], ...],
) -> MessagePlan:
    """Build a body-free, provenance-only plan for a future composer."""
    trigger = resolved.trigger
    customer_id = resolved.customer.customer_id if resolved.customer else None
    send_as = "merchant_on_behalf" if trigger.scope.value == "customer" else "vera"
    rationale_bits = [
        f"Selected {trigger.kind} because the trigger is active and contains required grounded evidence",
    ]
    if resolved.customer is not None:
        rationale_bits.append("the resolved customer belongs to the merchant and passed consent evaluation")
    if selected_offer is not None:
        rationale_bits.append("a real active merchant offer is available")
    rationale_bits.append(f"strategy is {rule.strategy}")
    metadata = score_components + (("opportunity_score", str(score)), ("category_version", str(resolved.category.version)), ("merchant_version", str(resolved.merchant.version)), ("trigger_version", str(trigger.version)))
    if resolved.customer is not None:
        metadata += (("customer_version", str(resolved.customer.version)),)
    return MessagePlan(
        should_send=True,
        target_scope=trigger.scope,
        trigger_id=trigger.trigger_id,
        trigger_kind=trigger.kind,
        merchant_id=resolved.merchant.merchant_id,
        customer_id=customer_id,
        selected_facts=tuple(facts),
        selected_offer=selected_offer,
        hook_type=rule.hook_type,
        strategy=rule.strategy,
        cta_strategy=rule.cta_strategy,
        send_as=send_as,
        suppression_key=trigger.suppression_key,
        rationale="; ".join(rationale_bits) + ".",
        decision_metadata=metadata,
    )
