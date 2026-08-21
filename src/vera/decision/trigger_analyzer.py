from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

from vera.context.validation import has_value, is_placeholder_payload, parse_iso8601
from vera.decision.opportunity import OpportunityRule, get_rule
from vera.domain.enums import NoActionReason
from vera.domain.models import ContextValidationError, ResolvedContext


@dataclass(frozen=True)
class TriggerAnalysis:
    kind: str
    scope: str
    source: str
    urgency: int
    expired: bool
    payload_placeholder: bool
    evidence_fields: Tuple[str, ...]
    actionable: bool
    no_action_reason: NoActionReason | None
    rationale: str
    rule: OpportunityRule | None


class TriggerAnalyzer:
    """Turns a typed trigger into an evidence assessment, never a message."""

    def analyze(self, resolved: ResolvedContext, now: datetime) -> TriggerAnalysis:
        trigger = resolved.trigger
        rule = get_rule(trigger.kind)
        try:
            expired = parse_iso8601(trigger.expires_at) <= now
        except ContextValidationError:
            return self._no_action(trigger, rule, False, False, (), NoActionReason.CONTEXT_VALIDATION_ERROR, "trigger expiry is malformed")
        if expired:
            return self._no_action(trigger, rule, True, False, (), NoActionReason.EXPIRED_TRIGGER, "trigger expiry has passed")
        if rule is None:
            return self._no_action(trigger, None, False, False, (), NoActionReason.UNSUPPORTED_TRIGGER_KIND, f"no opportunity rule exists for {trigger.kind}")
        if rule.scope != trigger.scope:
            return self._no_action(trigger, rule, False, False, (), NoActionReason.TRIGGER_SCOPE_INVALID, "trigger scope conflicts with its opportunity rule")
        payload = trigger.event_payload
        if is_placeholder_payload(payload):
            return self._no_action(
                trigger,
                rule,
                False,
                True,
                (),
                NoActionReason.PLACEHOLDER_EVIDENCE,
                "trigger payload is a generated placeholder and contains no message evidence",
            )
        evidence = tuple(path for path in rule.required_all if has_value(payload, path))
        missing = tuple(path for path in rule.required_all if path not in evidence)
        if missing:
            return self._no_action(
                trigger,
                rule,
                False,
                False,
                evidence,
                NoActionReason.INSUFFICIENT_EVIDENCE,
                f"trigger lacks required evidence: {', '.join(missing)}",
            )
        if rule.required_any and not any(has_value(payload, path) for path in rule.required_any):
            return self._no_action(
                trigger,
                rule,
                False,
                False,
                evidence,
                NoActionReason.INSUFFICIENT_EVIDENCE,
                f"trigger lacks one of: {', '.join(rule.required_any)}",
            )
        return TriggerAnalysis(
            kind=trigger.kind,
            scope=trigger.scope.value,
            source=trigger.source.value,
            urgency=trigger.urgency,
            expired=False,
            payload_placeholder=False,
            evidence_fields=evidence,
            actionable=True,
            no_action_reason=None,
            rationale=f"{trigger.kind} has required grounded evidence",
            rule=rule,
        )

    @staticmethod
    def _no_action(
        trigger,
        rule: OpportunityRule | None,
        expired: bool,
        payload_placeholder: bool,
        evidence: Tuple[str, ...],
        reason: NoActionReason,
        rationale: str,
    ) -> TriggerAnalysis:
        return TriggerAnalysis(
            kind=trigger.kind,
            scope=trigger.scope.value,
            source=trigger.source.value,
            urgency=trigger.urgency,
            expired=expired,
            payload_placeholder=payload_placeholder,
            evidence_fields=evidence,
            actionable=False,
            no_action_reason=reason,
            rationale=rationale,
            rule=rule,
        )
