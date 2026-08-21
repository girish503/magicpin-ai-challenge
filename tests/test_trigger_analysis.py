from conftest import seed_merchant_context, trigger_payload
from vera.context.resolver import ContextResolver
from vera.context.store import ContextStore
from vera.decision.opportunity import OPPORTUNITY_RULES
from vera.decision.trigger_analyzer import TriggerAnalyzer
from vera.domain.enums import NoActionReason


def resolved_trigger(payload):
    store = ContextStore()
    seed_merchant_context(store)
    store.put("trigger", payload["id"], 1, payload)
    trigger = store.get_trigger(payload["id"])
    return ContextResolver(store).resolve(None, "m-1", trigger)


def test_trigger_analyzer_accepts_complete_perf_dip_evidence(now):
    resolved = resolved_trigger(
        trigger_payload(event_payload={"metric": "views", "delta_pct": -10, "window": "7d"})
    )

    analysis = TriggerAnalyzer().analyze(resolved, now)

    assert analysis.actionable
    assert analysis.rule is OPPORTUNITY_RULES["perf_dip"]
    assert analysis.evidence_fields == ("metric", "delta_pct", "window")


def test_trigger_analyzer_rejects_missing_required_evidence(now):
    resolved = resolved_trigger(trigger_payload(event_payload={"metric": "views"}))

    analysis = TriggerAnalyzer().analyze(resolved, now)

    assert not analysis.actionable
    assert analysis.no_action_reason == NoActionReason.INSUFFICIENT_EVIDENCE


def test_trigger_analyzer_rejects_unknown_kind(now):
    resolved = resolved_trigger(
        trigger_payload(kind="unknown_kind", event_payload={"fact": "known"})
    )

    analysis = TriggerAnalyzer().analyze(resolved, now)

    assert analysis.no_action_reason == NoActionReason.UNSUPPORTED_TRIGGER_KIND


def test_all_known_opportunity_rules_have_a_trigger_scope():
    assert OPPORTUNITY_RULES
    assert all(rule.scope.value in {"merchant", "customer"} for rule in OPPORTUNITY_RULES.values())
