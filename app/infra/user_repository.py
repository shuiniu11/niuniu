"""User repository with placeholders for aggregated behavioral and AI features."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class UserAggregatedFeatures:
    """Aggregated user behavioral and AI-related metrics."""

    user_id: str
    common_ip: Optional[str]
    comment_count: int
    avg_similarity: float
    first_comment_time: Optional[dt.datetime]
    last_comment_time: Optional[dt.datetime]
    active_days: int
    sources: List[str]
    ai_labeled_ratio: float
    avg_ai_probability: Optional[float]
    high_ai_prob_ratio: Optional[float]
    avg_perplexity: Optional[float]
    avg_burstiness: Optional[float]


class UserRepository:
    """Repository providing access to user aggregated features.

    The current implementation is a placeholder; replace with real DB access when ready.
    """

    def __init__(self) -> None:
        # TODO: inject DB session/engine when wiring up real persistence.
        self._fallback_cache: Dict[str, UserAggregatedFeatures] = {}

    async def get_aggregated_features(
        self, user_ids: List[str], window_hours: int = 72
    ) -> Dict[str, UserAggregatedFeatures]:
        """Fetch aggregated behavior and AI features for the given users.

        The real implementation should join User, Comment, AI_Feature tables, filtered by
        `Comment.post_time >= now() - interval 'window_hours hours'`, and compute grouped
        aggregates. Placeholder logic returns safe defaults.

        Conceptual SQL (to be implemented via ORM/SQLBuilder):

        ```sql
        SELECT
            u.user_id,
            u.common_ip,
            u.comment_count,
            u.avg_similarity,
            MIN(c.post_time) AS first_comment_time,
            MAX(c.post_time) AS last_comment_time,
            COUNT(DISTINCT DATE(c.post_time)) AS active_days,
            ARRAY_AGG(DISTINCT c.source) AS sources,
            AVG(CASE WHEN c.is_ai_label THEN 1 ELSE 0 END) AS ai_labeled_ratio,
            AVG(f.ai_probability) AS avg_ai_probability,
            AVG(CASE WHEN f.ai_probability >= 0.8 THEN 1 ELSE 0 END) AS high_ai_prob_ratio,
            AVG(f.perplexity) AS avg_perplexity,
            AVG(f.burstiness) AS avg_burstiness
        FROM user AS u
        LEFT JOIN comment AS c ON c.user_id = u.user_id
            AND c.post_time >= NOW() - INTERVAL '%(window_hours)s hours'
        LEFT JOIN ai_feature AS f ON f.comment_id = c.comment_id
        WHERE u.user_id IN (:user_ids)
        GROUP BY u.user_id, u.common_ip, u.comment_count, u.avg_similarity;
        ```
        """

        default_features: Dict[str, UserAggregatedFeatures] = {}

        for user_id in user_ids:
            cached = self._fallback_cache.get(user_id)
            if cached:
                default_features[user_id] = cached
                continue

            default_features[user_id] = UserAggregatedFeatures(
                user_id=user_id,
                common_ip=None,
                comment_count=0,
                avg_similarity=0.0,
                first_comment_time=None,
                last_comment_time=None,
                active_days=0,
                sources=[],
                ai_labeled_ratio=0.0,
                avg_ai_probability=None,
                high_ai_prob_ratio=0.0,
                avg_perplexity=None,
                avg_burstiness=None,
            )

        # TODO: replace with actual DB fetch. This fallback simply returns defaults.
        return default_features

    def bulk_get_features(self, user_ids: List[str]) -> Dict[str, Dict[str, str]]:
        """Deprecated: retained for backward compatibility with legacy callers."""

        return {user_id: {"note": "deprecated mock"} for user_id in user_ids}
