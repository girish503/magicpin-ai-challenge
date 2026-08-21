from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from vera.context.store import ContextStore
from vera.dataset import load_expanded_dataset
from vera.decision.ranker import DeterministicRanker
from vera.context.resolver import ContextResolver
from vera.domain.enums import DecisionStatus, NoActionReason


def build_domain_core_report(dataset_root: Path, now: datetime) -> Dict[str, Any]:
    store = ContextStore()
    load_expanded_dataset(store, dataset_root)
    ranker = DeterministicRanker(ContextResolver(store))
    counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    for trigger_id in sorted(store.get_trigger(trigger_id).trigger_id for trigger_id in _ids(store, "trigger")):
        trigger = store.get_trigger(trigger_id)
        assert trigger is not None
        kind_counts[trigger.kind] += 1
        result = ranker.decide(None, trigger.merchant_id, trigger, now, trigger.customer_id)
        if result.status == DecisionStatus.SELECTED:
            counts["actionable_triggers"] += 1
        else:
            counts["no_action_triggers"] += 1
            if result.no_action_reason is not None:
                counts[f"reason:{result.no_action_reason.value}"] += 1
    return {
        "total_triggers": sum(kind_counts.values()),
        "actionable_triggers": counts["actionable_triggers"],
        "no_action_triggers": counts["no_action_triggers"],
        "unresolved_contexts": counts["reason:missing_merchant_context"] + counts["reason:missing_category_context"] + counts["reason:missing_customer_context"] + counts["reason:trigger_merchant_mismatch"] + counts["reason:merchant_customer_mismatch"],
        "consent_rejections": counts["reason:consent_rejected"],
        "suppression_rejections": counts["reason:suppressed"] + counts["reason:duplicate_in_conversation"] + counts["reason:conversation_terminal"],
        "placeholder_triggers": counts["reason:placeholder_evidence"],
        "trigger_kind_counts": dict(sorted(kind_counts.items())),
        "no_action_reason_counts": {key.removeprefix("reason:"): value for key, value in sorted(counts.items()) if key.startswith("reason:")},
        "context_counts": store.counts(),
    }


def write_domain_core_report(dataset_root: Path, report_path: Path, now: datetime) -> Dict[str, Any]:
    import json

    report = build_domain_core_report(dataset_root, now)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _ids(store: ContextStore, scope: str) -> list[str]:
    from vera.domain.enums import ContextScope

    return [context_id for (stored_scope, context_id) in store._records if stored_scope == ContextScope(scope)]
