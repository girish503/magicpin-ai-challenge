from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    payload: dict[str, Any]
    delivered_at: str = Field(min_length=1)


class ContextAcceptedResponse(BaseModel):
    accepted: Literal[True]
    ack_id: str
    stored_at: str


class ContextConflictResponse(BaseModel):
    accepted: Literal[False]
    reason: Literal["stale_version"]
    current_version: int


class TickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    now: str = Field(min_length=1)
    available_triggers: list[str] = Field(default_factory=list, max_length=100)


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: str | None
    send_as: Literal["vera", "merchant_on_behalf"]
    trigger_id: str
    template_name: str
    template_params: list[str]
    body: str = Field(min_length=1)
    cta: str
    suppression_key: str
    rationale: str = Field(min_length=1)


class TickResponse(BaseModel):
    actions: list[TickAction] = Field(max_length=20)


class ReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1)
    merchant_id: str = Field(min_length=1)
    customer_id: str | None = None
    from_role: Literal["merchant", "customer"]
    message: str = Field(min_length=1)
    received_at: str = Field(min_length=1)
    turn_number: int = Field(ge=1)


class SendReplyResponse(BaseModel):
    action: Literal["send"]
    body: str = Field(min_length=1)
    cta: str
    rationale: str = Field(min_length=1)


class WaitReplyResponse(BaseModel):
    action: Literal["wait"]
    wait_seconds: int = Field(gt=0)
    rationale: str = Field(min_length=1)


class EndReplyResponse(BaseModel):
    action: Literal["end"]
    rationale: str = Field(min_length=1)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    uptime_seconds: int = Field(ge=0)
    contexts_loaded: dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str
