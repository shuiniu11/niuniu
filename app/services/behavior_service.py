"""Service for analyzing user behavior risk using Deepseek LLM."""
from __future__ import annotations

import json
import logging
from typing import List

from app.infra.llm_client import LLMClient
from app.models.schemas import BehaviorAnalysisRequest, BehaviorAnalysisResponse, RiskLevel

logger = logging.getLogger(__name__)


class BehaviorAnalysisService:
    """Apply heuristic feature extraction and call LLM for risk analysis."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def analyze(self, payload: BehaviorAnalysisRequest) -> BehaviorAnalysisResponse:
        """Analyze a single user's behavior and return risk assessment."""

        prompt = self._build_prompt(payload)
        try:
            llm_result = await self.llm_client.analyze_behavior(prompt)
        except RuntimeError:
            llm_result = {
                "risk_score": 0.1,
                "risk_level": "low",
                "suspicious_factors": ["LLM 调用失败，使用默认低风险结果"],
                "advice": "保持观察"
            }

        risk_score = self._clip_score(llm_result.get("risk_score", 0.0))
        risk_level = self._normalize_risk_level(llm_result.get("risk_level"))
        suspicious_factors: List[str] = llm_result.get("suspicious_factors", [])
        advice = llm_result.get("advice", "")

        return BehaviorAnalysisResponse(
            user_id=payload.user_id,
            risk_score=risk_score,
            risk_level=risk_level,
            suspicious_factors=suspicious_factors,
            advice=advice,
        )

    def _build_prompt(self, payload: BehaviorAnalysisRequest) -> str:
        """Construct the prompt for Deepseek LLM."""

        comments_sample = payload.comments[:10]
        unique_comments = list(dict.fromkeys(payload.comments))
        comments_dedup_count = len(unique_comments)

        recent_comments = payload.extra.comments_last_24h if payload.extra else None
        register_time = payload.extra.register_time.isoformat() if payload.extra and payload.extra.register_time else "unknown"
        last_login_time = payload.extra.last_login_time.isoformat() if payload.extra and payload.extra.last_login_time else "unknown"

        prompt_payload = {
            "user_id": payload.user_id,
            "comment_samples": comments_sample,
            "comment_dedup_count": comments_dedup_count,
            "comments_last_24h": recent_comments,
            "ip_stats": {
                "count": len(payload.ip_history),
                "unique": len(set(payload.ip_history)),
            },
            "device_stats": {
                "count": len(payload.device_ids),
                "unique": len(set(payload.device_ids)),
            },
            "register_time": register_time,
            "last_login_time": last_login_time,
        }

        instruction = (
            "你是一个内容平台的风控助手，请根据以下用户信息判断其是否为水军账号。"\
            "只输出 JSON，格式如下：{\n"
            "  \"risk_score\": <0到1之间的浮点数>,\n"
            "  \"risk_level\": \"low|medium|high\",\n"
            "  \"suspicious_factors\": [\"字符串列表\"],\n"
            "  \"advice\": \"简短建议\"\n"
            "}。不要输出其他解释。"
        )

        prompt = f"{instruction}\n输入:\n{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
        logger.debug("Behavior analysis prompt: %s", prompt)
        return prompt

    @staticmethod
    def _clip_score(value: float) -> float:
        """Ensure risk score is within [0, 1]."""

        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, number))

    @staticmethod
    def _normalize_risk_level(value: str | None) -> RiskLevel:
        """Normalize risk level to allowed values."""

        try:
            level = value.lower() if value else RiskLevel.LOW.value
        except AttributeError:
            level = RiskLevel.LOW.value

        if level not in {risk.value for risk in RiskLevel}:
            return RiskLevel.LOW
        return RiskLevel(level)
