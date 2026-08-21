from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from itertools import count
from typing import Any

from vera.context.resolver import ContextResolver
from vera.context.store import ContextStore
from vera.context.validation import parse_iso8601
from vera.conversation.machine import ConversationMachine
from vera.decision.ranker import DeterministicRanker
from vera.domain.enums import ConversationStatus, ContextScope, DecisionStatus, Intent, StoreUpdateStatus
from vera.domain.models import ContextValidationError, ConversationState, MessagePlan
from vera.policy.suppression import SuppressionRegistry

from app.models import (
    ContextAcceptedResponse,
    ContextConflictResponse,
    ContextRequest,
    EndReplyResponse,
    HealthResponse,
    MetadataResponse,
    ReplyRequest,
    SendReplyResponse,
    TickAction,
    TickRequest,
    TickResponse,
    WaitReplyResponse,
)


class ContextInputError(ValueError):
    def __init__(self, reason: str, details: str) -> None:
        super().__init__(details)
        self.reason = reason
        self.details = details


class ContextConflictError(ValueError):
    def __init__(self, current_version: int) -> None:
        super().__init__("context version is not newer than the stored version")
        self.current_version = current_version


class RuntimeService:
    def __init__(self) -> None:
        self.store = ContextStore()
        self.resolver = ContextResolver(self.store)
        self.suppression = SuppressionRegistry()
        self.ranker = DeterministicRanker(self.resolver, self.suppression)
        self.conversations: dict[str, ConversationState] = {}
        self._conversation_ids = count(1)
        self._started_at = time.monotonic()

    def health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            uptime_seconds=int(time.monotonic() - self._started_at),
            contexts_loaded=self.store.counts(),
        )

    def metadata(self) -> MetadataResponse:
        return MetadataResponse(
            team_name="Vera Challenge Team",
            team_members=[],
            model="deterministic-no-llm",
            approach="FastAPI adapter over the deterministic Vera domain core",
            contact_email="not-configured",
            version="0.1.0",
            submitted_at="2026-08-21T00:00:00Z",
        )

    def ingest_context(
        self, request: ContextRequest
    ) -> ContextAcceptedResponse | ContextConflictResponse:
        try:
            scope = ContextScope(request.scope)
        except ValueError as exc:
            raise ContextInputError("invalid_scope", f"unsupported context scope: {request.scope!r}") from exc
        try:
            parse_iso8601(request.delivered_at)
            result = self.store.put(
                scope,
                request.context_id,
                request.version,
                request.payload,
                delivered_at=request.delivered_at,
            )
        except (ContextValidationError, ValueError) as exc:
            raise ContextInputError("invalid_context", str(exc)) from exc
        if result.status in {StoreUpdateStatus.IDEMPOTENT, StoreUpdateStatus.STALE}:
            raise ContextConflictError(result.current_version)
        return ContextAcceptedResponse(
            accepted=True,
            ack_id=f"ack_{request.context_id}_v{request.version}",
            stored_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    def tick(self, request: TickRequest) -> TickResponse:
        try:
            now = parse_iso8601(request.now)
        except ContextValidationError as exc:
            raise ContextInputError("invalid_now", str(exc)) from exc

        actions: list[TickAction] = []
        seen_trigger_ids: set[str] = set()
        for trigger_id in request.available_triggers:
            if trigger_id in seen_trigger_ids or len(actions) >= 20:
                continue
            seen_trigger_ids.add(trigger_id)
            trigger = self.store.get_trigger(trigger_id)
            if trigger is None:
                continue
            result = self.ranker.decide(
                None,
                trigger.merchant_id,
                trigger,
                now,
                trigger.customer_id,
            )
            if result.status != DecisionStatus.SELECTED or result.plan is None:
                continue
            action = self._action_from_plan(result.plan)
            conversation_id = action.conversation_id
            state = ConversationMachine.new(
                conversation_id,
                action.merchant_id,
                action.customer_id,
            )
            self.conversations[conversation_id] = ConversationMachine.record_outbound(
                state,
                action.body,
                action.trigger_id,
                request.now,
                1,
            )
            self.ranker.commit_selected(result, now)
            actions.append(action)
        return TickResponse(actions=actions)

    def reply(self, request: ReplyRequest) -> SendReplyResponse | WaitReplyResponse | EndReplyResponse:
        state = self.conversations.get(request.conversation_id)
        if state is None:
            return EndReplyResponse(
                action="end",
                rationale="Conversation is unknown; ending without inventing context.",
            )
        if state.merchant_id != request.merchant_id or state.customer_id != request.customer_id:
            raise ContextInputError("conversation_mismatch", "conversation recipient does not match stored state")
        try:
            parse_iso8601(request.received_at)
        except ContextValidationError as exc:
            raise ContextInputError("invalid_received_at", str(exc)) from exc

        updated = ConversationMachine.receive_reply(
            state,
            request.message,
            request.received_at,
            request.turn_number,
        )
        self.conversations[request.conversation_id] = updated

        if updated.current_intent == Intent.STOP or updated.status in {
            ConversationStatus.COMPLETED,
            ConversationStatus.SUPPRESSED,
        }:
            return EndReplyResponse(
                action="end",
                rationale="Conversation reached a terminal state through the deterministic conversation policy.",
            )
        if updated.current_intent == Intent.AUTO_REPLY:
            return WaitReplyResponse(
                action="wait",
                wait_seconds=14400,
                rationale="Detected a canned auto-reply; backing off while waiting for the owner.",
            )
        if updated.current_intent == Intent.DEFER:
            return WaitReplyResponse(
                action="wait",
                wait_seconds=1800,
                rationale="The recipient asked to defer; backing off for 30 minutes.",
            )
        if updated.current_intent == Intent.COMMITMENT:
            body = "Understood. I will move to the next step for this conversation."
            self.conversations[request.conversation_id] = ConversationMachine.record_outbound(
                updated,
                body,
                updated.last_trigger_id or "reply",
                request.received_at,
                request.turn_number + 1,
            )
            return SendReplyResponse(
                action="send",
                body=body,
                cta="binary_confirm_cancel",
                rationale="The recipient explicitly committed, so the conversation moves directly to execution.",
            )
        return SendReplyResponse(
            action="send",
            body="Thanks. Please tell me the next step you want to take.",
            cta="open_ended",
            rationale="The deterministic conversation policy kept the conversation active and requested the next actionable detail.",
        )

    def _action_from_plan(self, plan: MessagePlan) -> TickAction:
        conversation_id = f"conv_{plan.merchant_id}_{next(self._conversation_ids)}"
        name = self._fact_value(plan, "identity.name") or self._fact_value(plan, "identity.language_pref") or plan.merchant_id
        detail_values = [
            self._format_value(fact.value)
            for fact in plan.selected_facts
            if not fact.path.endswith("identity.name")
            and not fact.path.endswith("identity.owner_first_name")
            and fact.value is not None
        ]
        detail = detail_values[0] if detail_values else plan.trigger_kind.replace("_", " ")
        body = f"{name}, this is about {plan.trigger_kind.replace('_', ' ')}. {detail}. Reply yes to continue."
        template_name = f"vera_{plan.trigger_kind}_v1"
        template_params = [str(name), str(detail)]
        return TickAction(
            conversation_id=conversation_id,
            merchant_id=plan.merchant_id,
            customer_id=plan.customer_id,
            send_as=plan.send_as,
            trigger_id=plan.trigger_id,
            template_name=template_name,
            template_params=template_params,
            body=body,
            cta=plan.cta_strategy,
            suppression_key=plan.suppression_key,
            rationale=plan.rationale,
        )

    @staticmethod
    def _fact_value(plan: MessagePlan, path: str) -> Any:
        for fact in plan.selected_facts:
            if fact.path == path:
                return fact.value
        return None

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=True, sort_keys=True)
        return str(value)
