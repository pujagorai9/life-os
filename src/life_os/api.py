from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from life_os.agent_catalog import list_agents
from life_os.analytics import build_progress_summary
from life_os.config import load_profile
from life_os.models import (
    AgentDefinition,
    AgentOutput,
    ChatRequest,
    Commitment,
    CommitmentCreate,
    CommitmentStatus,
    Memory,
    MemoryCreate,
    ProgressEvent,
    ProgressEventCreate,
    ProgressSummary,
)
from life_os.orchestrator import LifeOS
from life_os.store import LifeOSStore


def create_app(database: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Life OS", version="0.1.0")
    store = LifeOSStore(database or os.getenv("LIFE_OS_DATABASE", "life_os.db"))
    runtime = LifeOS(store=store, profile=load_profile())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/agents", response_model=list[AgentDefinition])
    def agents() -> list[AgentDefinition]:
        return list_agents()

    @app.post("/v1/chat", response_model=AgentOutput)
    def chat(request: ChatRequest) -> AgentOutput:
        return runtime.chat(request)

    @app.post("/v1/commitments", response_model=Commitment)
    def create_commitment(request: CommitmentCreate) -> Commitment:
        return store.create_commitment(request)

    @app.patch("/v1/commitments/{commitment_id}", response_model=Commitment)
    def update_commitment(
        commitment_id: str,
        tenant_id: str = Query(...),
        status: CommitmentStatus = Query(...),
    ) -> Commitment:
        try:
            return store.update_commitment_status(tenant_id, commitment_id, status)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/events", response_model=ProgressEvent)
    def create_event(request: ProgressEventCreate) -> ProgressEvent:
        return store.create_event(request)

    @app.get("/v1/progress", response_model=ProgressSummary)
    def progress(tenant_id: str = Query(...)) -> ProgressSummary:
        return build_progress_summary(store, tenant_id)

    @app.post("/v1/memories", response_model=Memory)
    def propose_memory(request: MemoryCreate) -> Memory:
        return store.propose_memory(request)

    @app.post("/v1/memories/{memory_id}/confirm", response_model=Memory)
    def confirm_memory(memory_id: str, tenant_id: str = Query(...)) -> Memory:
        try:
            return store.confirm_memory(tenant_id, memory_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return app


app = create_app()
