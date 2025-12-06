"""API route definitions for the FastAPI application."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import (
    BehaviorAnalysisRequest,
    BehaviorAnalysisResponse,
    ClusterDetectionRequest,
    ClusterDetectionResponse,
)
from app.services.behavior_service import BehaviorAnalysisService
from app.services.cluster_service import ClusterDetectionService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_behavior_service() -> BehaviorAnalysisService:
    from app.main import behavior_service

    return behavior_service


def get_cluster_service() -> ClusterDetectionService:
    from app.main import cluster_service

    return cluster_service


@router.post("/analyze_behavior", response_model=BehaviorAnalysisResponse)
async def analyze_behavior(
    payload: BehaviorAnalysisRequest,
    service: BehaviorAnalysisService = Depends(get_behavior_service),
) -> BehaviorAnalysisResponse:
    """Analyze whether a single user shows bot-like behavior."""

    try:
        return await service.analyze(payload)
    except ValueError as exc:
        logger.exception("Invalid input for behavior analysis: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/detect_cluster", response_model=ClusterDetectionResponse)
async def detect_cluster(
    payload: ClusterDetectionRequest,
    service: ClusterDetectionService = Depends(get_cluster_service),
) -> ClusterDetectionResponse:
    """Detect suspicious clusters from a list of user IDs."""

    try:
        return await service.detect(payload)
    except ValueError as exc:
        logger.exception("Invalid input for cluster detection: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
