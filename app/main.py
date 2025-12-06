"""FastAPI application entry point."""
from __future__ import annotations

import logging
from fastapi import FastAPI

from app.api.routes import router as api_router
from app.infra.llm_client import LLMClient
from app.infra.user_repository import UserRepository
from app.services.behavior_service import BehaviorAnalysisService
from app.services.cluster_service import ClusterDetectionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm_client = LLMClient()
behavior_service = BehaviorAnalysisService(llm_client)
user_repository = UserRepository()
cluster_service = ClusterDetectionService(user_repository)

app = FastAPI(title="Anti-Bot Risk Detection Service")
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}
