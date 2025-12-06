"""Pydantic request and response schemas for the anti-bot risk service."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class RiskLevel(str, Enum):
    """Risk level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BehaviorExtra(BaseModel):
    """Additional metadata for user behavior analysis."""

    register_time: Optional[datetime] = Field(None, description="User registration timestamp")
    last_login_time: Optional[datetime] = Field(None, description="User last login timestamp")
    comments_last_24h: Optional[int] = Field(
        None, ge=0, description="Number of comments in the last 24 hours"
    )


class BehaviorAnalysisRequest(BaseModel):
    """Request body for analyzing a single user's behavior."""

    user_id: str = Field(..., description="Unique user identifier")
    comments: List[str] = Field(..., description="List of user comments")
    ip_history: List[str] = Field(..., description="List of IP addresses used by the user")
    device_ids: List[str] = Field(..., description="List of device identifiers used by the user")
    extra: Optional[BehaviorExtra] = Field(
        default=None, description="Extra metadata such as registration time"
    )

    @validator("comments", "ip_history", "device_ids")
    def non_empty_list(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("List must not be empty")
        return value


class BehaviorAnalysisResponse(BaseModel):
    """Response for user behavior analysis."""

    user_id: str
    risk_score: float
    risk_level: RiskLevel
    suspicious_factors: List[str]
    advice: str


class ClusterDetectionRequest(BaseModel):
    """Request body for detecting suspicious clusters."""

    user_ids: List[str] = Field(..., description="List of user IDs to inspect")

    @validator("user_ids")
    def non_empty_user_ids(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("user_ids must not be empty")
        return value


class ClusterInfo(BaseModel):
    """Information about a detected cluster."""

    cluster_id: str
    user_ids: List[str]
    size: int
    avg_similarity: float
    shared_ip_ratio: float
    shared_device_ratio: float
    risk_score: float
    risk_level: RiskLevel
    description: str


class ClusterDetectionResponse(BaseModel):
    """Response for cluster detection."""

    clusters: List[ClusterInfo]
    overall_risk_level: RiskLevel
