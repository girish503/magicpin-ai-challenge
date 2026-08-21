from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.models import (
    ContextAcceptedResponse,
    ContextConflictResponse,
    ContextRequest,
    EndReplyResponse,
    HealthResponse,
    MetadataResponse,
    ReplyRequest,
    SendReplyResponse,
    TickRequest,
    TickResponse,
    WaitReplyResponse,
)
from app.runtime import ContextConflictError, ContextInputError, RuntimeService



def create_app() -> FastAPI:
    application = FastAPI(title="Vera deterministic runtime", version="0.1.0")
    application.state.runtime = RuntimeService()

    @application.get("/v1/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return application.state.runtime.health()

    @application.get("/v1/metadata", response_model=MetadataResponse)
    def metadata() -> MetadataResponse:
        return application.state.runtime.metadata()

    @application.post(
        "/v1/context",
        response_model=ContextAcceptedResponse | ContextConflictResponse,
        status_code=200,
    )
    def push_context(request: ContextRequest):
        try:
            return application.state.runtime.ingest_context(request)
        except ContextConflictError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "accepted": False,
                    "reason": "stale_version",
                    "current_version": exc.current_version,
                },
            )
        except ContextInputError as exc:
            return JSONResponse(
                status_code=400,
                content={"accepted": False, "reason": exc.reason, "details": exc.details},
            )

    @application.post("/v1/tick", response_model=TickResponse)
    def tick(request: TickRequest):
        try:
            return application.state.runtime.tick(request)
        except ContextInputError as exc:
            return JSONResponse(status_code=400, content={"reason": exc.reason, "details": exc.details})

    @application.post(
        "/v1/reply",
        response_model=SendReplyResponse | WaitReplyResponse | EndReplyResponse,
    )
    def reply(request: ReplyRequest):
        try:
            return application.state.runtime.reply(request)
        except ContextInputError as exc:
            return JSONResponse(status_code=400, content={"reason": exc.reason, "details": exc.details})

    return application


app = create_app()
