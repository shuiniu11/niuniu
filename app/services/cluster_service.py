"""Service for detecting suspicious bot clusters based on behavioral heuristics."""
from __future__ import annotations

import logging
import math
import uuid
from collections import deque
from itertools import combinations
from typing import Dict, Iterable, List, Set, Tuple, Optional

from app.infra.user_repository import UserAggregatedFeatures, UserRepository
from app.models.schemas import (
    ClusterDetectionRequest,
    ClusterDetectionResponse,
    ClusterInfo,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Weights for pairwise similarity components
W_IP = 3.0
W_ACTIVITY = 2.0
W_SOURCE = 1.0
W_AI = 3.0
W_INTENSITY = 1.0
EDGE_THRESHOLD = 0.7


class ClusterDetectionService:
    """Detect suspicious bot clusters using aggregated behavioral signals."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def detect(self, payload: ClusterDetectionRequest) -> ClusterDetectionResponse:
        """Detect suspicious clusters from the provided user IDs."""

        features = await self.user_repository.get_aggregated_features(payload.user_ids)
        adjacency, pair_scores = self._build_similarity_graph(features, window_hours=72)
        cluster_user_lists = self._extract_clusters(adjacency, include_singletons=True)

        clusters: List[ClusterInfo] = []
        for user_ids in cluster_user_lists:
            cluster = self._build_cluster_info(user_ids, features, pair_scores)
            clusters.append(cluster)

        overall = self._overall_risk_level(clusters)
        return ClusterDetectionResponse(clusters=clusters, overall_risk_level=overall)

    def _build_similarity_graph(
        self, features: Dict[str, UserAggregatedFeatures], window_hours: int
    ) -> Tuple[Dict[str, List[Tuple[str, float]]], Dict[Tuple[str, str], float]]:
        """Construct an undirected similarity graph between users."""

        adjacency: Dict[str, List[Tuple[str, float]]] = {user_id: [] for user_id in features}
        pair_scores: Dict[Tuple[str, str], float] = {}

        for u_id, v_id in combinations(features.keys(), 2):
            score = self._pair_similarity(features[u_id], features[v_id], window_hours)
            pair_scores[tuple(sorted((u_id, v_id)))] = score
            if score >= EDGE_THRESHOLD:
                adjacency[u_id].append((v_id, score))
                adjacency[v_id].append((u_id, score))

        return adjacency, pair_scores

    def _pair_similarity(
        self, f1: UserAggregatedFeatures, f2: UserAggregatedFeatures, window_hours: int
    ) -> float:
        """Compute the weighted pairwise similarity between two users."""

        ip_score = 1.0 if f1.common_ip and f1.common_ip == f2.common_ip else 0.0
        activity_score = self._activity_overlap_score(f1, f2, window_hours)
        source_score = self._source_overlap_score(f1.sources, f2.sources)
        ai_profile_score = self._ai_profile_score(f1, f2)
        intensity_score = self._intensity_score(f1.comment_count, f2.comment_count)

        weighted = (
            W_IP * ip_score
            + W_ACTIVITY * activity_score
            + W_SOURCE * source_score
            + W_AI * ai_profile_score
            + W_INTENSITY * intensity_score
        )
        return weighted / (W_IP + W_ACTIVITY + W_SOURCE + W_AI + W_INTENSITY)

    @staticmethod
    def _activity_overlap_score(
        f1: UserAggregatedFeatures, f2: UserAggregatedFeatures, window_hours: int
    ) -> float:
        """Estimate activity overlap based on recent comment intervals."""

        if not f1.first_comment_time or not f1.last_comment_time:
            return 0.0
        if not f2.first_comment_time or not f2.last_comment_time:
            return 0.0

        start = max(f1.first_comment_time, f2.first_comment_time)
        end = min(f1.last_comment_time, f2.last_comment_time)
        overlap_seconds = (end - start).total_seconds()
        if overlap_seconds <= 0:
            return 0.0

        overlap_hours = overlap_seconds / 3600.0
        union_start = min(f1.first_comment_time, f2.first_comment_time)
        union_end = max(f1.last_comment_time, f2.last_comment_time)
        union_hours = max((union_end - union_start).total_seconds() / 3600.0, 1e-6)
        window = float(window_hours)
        normalized = min(overlap_hours / union_hours, overlap_hours / max(window, 1e-6))
        return max(0.0, min(1.0, normalized))

    @staticmethod
    def _source_overlap_score(sources_a: List[str], sources_b: List[str]) -> float:
        """Compute overlap ratio between source sets."""

        set_a, set_b = set(sources_a), set(sources_b)
        if not set_a or not set_b:
            return 0.0
        shared = len(set_a & set_b)
        return shared / min(len(set_a), len(set_b))

    @staticmethod
    def _scalar_similarity(a: Optional[float], b: Optional[float], max_diff: float) -> float:
        """Return similarity between two scalars within a tolerance bound."""

        if a is None or b is None:
            return 0.0
        diff = abs(a - b)
        if diff >= max_diff:
            return 0.0
        return 1.0 - diff / max_diff

    def _ai_profile_score(self, f1: UserAggregatedFeatures, f2: UserAggregatedFeatures) -> float:
        """Combine AI-related metrics into an averaged similarity score."""

        components = [
            self._scalar_similarity(f1.avg_ai_probability, f2.avg_ai_probability, 0.5),
            self._scalar_similarity(f1.high_ai_prob_ratio, f2.high_ai_prob_ratio, 0.5),
            self._scalar_similarity(f1.ai_labeled_ratio, f2.ai_labeled_ratio, 0.5),
            self._scalar_similarity(f1.avg_perplexity, f2.avg_perplexity, 30.0),
            self._scalar_similarity(f1.avg_burstiness, f2.avg_burstiness, 30.0),
            self._scalar_similarity(f1.avg_similarity, f2.avg_similarity, 0.5),
        ]
        if not components:
            return 0.0
        return sum(components) / len(components)

    def _intensity_score(self, c1: int, c2: int) -> float:
        """Compare comment intensity using log-scaled counts."""

        if c1 <= 0 or c2 <= 0:
            return 0.0
        v1 = math.log1p(c1)
        v2 = math.log1p(c2)
        return self._scalar_similarity(v1, v2, max_diff=2.0)

    def _extract_clusters(
        self, adjacency: Dict[str, List[Tuple[str, float]]], include_singletons: bool = True
    ) -> List[List[str]]:
        """Find connected components in the similarity graph."""

        visited: Set[str] = set()
        clusters: List[List[str]] = []

        for node in adjacency:
            if node in visited:
                continue
            if not adjacency[node] and not include_singletons:
                visited.add(node)
                continue

            queue: deque[str] = deque([node])
            visited.add(node)
            component: List[str] = []

            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor, _score in adjacency[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            if component and (include_singletons or len(component) > 1):
                clusters.append(component)

        return clusters

    def _build_cluster_info(
        self,
        user_ids: Iterable[str],
        features: Dict[str, UserAggregatedFeatures],
        pair_scores: Dict[Tuple[str, str], float],
    ) -> ClusterInfo:
        """Compute cluster metrics and risk level for a group of users."""

        users = list(user_ids)
        size = len(users)
        avg_similarity = self._cluster_avg_similarity(users, pair_scores)
        shared_ip_ratio = self._shared_ip_ratio(users, features)
        ai_heavy_ratio = self._ai_heavy_ratio(users, features)
        avg_user_similarity = self._avg_user_similarity(users, features)
        avg_comment_count = self._avg_comment_count(users, features)

        risk_score = self._compute_cluster_risk(
            size=size,
            avg_similarity=avg_similarity,
            shared_ip_ratio=shared_ip_ratio,
            ai_heavy_ratio=ai_heavy_ratio,
            avg_user_similarity=avg_user_similarity,
            avg_comment_count=avg_comment_count,
        )
        risk_level = self._risk_level_from_score(risk_score)
        description = self._build_cluster_description(
            size=size,
            avg_similarity=avg_similarity,
            shared_ip_ratio=shared_ip_ratio,
            ai_heavy_ratio=ai_heavy_ratio,
            risk_level=risk_level,
        )

        # No device info in current schema; placeholder at 0.0 for now.
        shared_device_ratio = 0.0

        cluster_id = f"c-{uuid.uuid4().hex[:8]}"
        return ClusterInfo(
            cluster_id=cluster_id,
            user_ids=users,
            size=size,
            avg_similarity=avg_similarity,
            shared_ip_ratio=shared_ip_ratio,
            shared_device_ratio=shared_device_ratio,
            risk_score=risk_score,
            risk_level=risk_level,
            description=description,
        )

    def _cluster_avg_similarity(
        self, user_ids: List[str], pair_scores: Dict[Tuple[str, str], float]
    ) -> float:
        """Average pairwise similarity for edges within the cluster."""

        scores: List[float] = []
        for u, v in combinations(sorted(user_ids), 2):
            score = pair_scores.get((u, v))
            if score is not None:
                scores.append(score)
        return sum(scores) / len(scores) if scores else 0.0

    def _shared_ip_ratio(
        self, user_ids: List[str], features: Dict[str, UserAggregatedFeatures]
    ) -> float:
        """Ratio of user pairs sharing the same non-null IP."""

        pairs = list(combinations(user_ids, 2))
        if not pairs:
            return 0.0

        shared_count = 0
        for u, v in pairs:
            ip_u = features[u].common_ip
            ip_v = features[v].common_ip
            if ip_u and ip_v and ip_u == ip_v:
                shared_count += 1
        return shared_count / len(pairs)

    @staticmethod
    def _ai_heavy_ratio(
        user_ids: List[str], features: Dict[str, UserAggregatedFeatures]
    ) -> float:
        """Average high AI probability ratio across users."""

        values: List[float] = []
        for user_id in user_ids:
            ratio = features[user_id].high_ai_prob_ratio
            if ratio is not None:
                values.append(ratio)
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _avg_user_similarity(
        user_ids: List[str], features: Dict[str, UserAggregatedFeatures]
    ) -> float:
        """Average content similarity score from the User table."""

        if not user_ids:
            return 0.0
        total = sum(features[user_id].avg_similarity for user_id in user_ids)
        return total / len(user_ids)

    @staticmethod
    def _avg_comment_count(
        user_ids: List[str], features: Dict[str, UserAggregatedFeatures]
    ) -> float:
        """Average comment count across users."""

        if not user_ids:
            return 0.0
        total = sum(features[user_id].comment_count for user_id in user_ids)
        return total / len(user_ids)

    @staticmethod
    def _compute_cluster_risk(
        size: int,
        avg_similarity: float,
        shared_ip_ratio: float,
        ai_heavy_ratio: float,
        avg_user_similarity: float,
        avg_comment_count: float,
    ) -> float:
        """Compute a composite cluster risk score in [0, 1]."""

        s_size = min(size / 20.0, 1.0)
        s_volume = min(math.log1p(avg_comment_count) / math.log1p(1000.0), 1.0)

        risk_score = (
            0.25 * s_size
            + 0.25 * avg_similarity
            + 0.15 * shared_ip_ratio
            + 0.2 * ai_heavy_ratio
            + 0.1 * avg_user_similarity
            + 0.05 * s_volume
        )
        return max(0.0, min(1.0, risk_score))

    @staticmethod
    def _risk_level_from_score(score: float) -> RiskLevel:
        """Map a numeric score to risk level buckets."""

        if score >= 0.8:
            return RiskLevel.HIGH
        if score >= 0.5:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _build_cluster_description(
        size: int,
        avg_similarity: float,
        shared_ip_ratio: float,
        ai_heavy_ratio: float,
        risk_level: RiskLevel,
    ) -> str:
        """Generate a short Chinese description for the cluster."""

        if risk_level == RiskLevel.HIGH:
            return (
                f"该集群包含 {size} 个账号，平均行为相似度为 {avg_similarity:.2f}，"
                f"IP 重合比例为 {shared_ip_ratio:.2f}，AI 文本特征明显（高 AI 概率比例为 {ai_heavy_ratio:.2f}），"
                "疑似高风险水军集群。"
            )
        if risk_level == RiskLevel.MEDIUM:
            return (
                f"该集群包含 {size} 个账号，行为特征相似度较高，IP 重合比例为 {shared_ip_ratio:.2f}，"
                f"高 AI 概率比例为 {ai_heavy_ratio:.2f}，存在水军嫌疑。"
            )
        return (
            f"该集群包含 {size} 个账号，行为相关性较弱，IP 重合和 AI 文本特征较少，"
            "整体风险较低。"
        )

    @staticmethod
    def _overall_risk_level(clusters: List[ClusterInfo]) -> RiskLevel:
        """Determine the highest risk level across clusters."""

        if any(cluster.risk_level == RiskLevel.HIGH for cluster in clusters):
            return RiskLevel.HIGH
        if any(cluster.risk_level == RiskLevel.MEDIUM for cluster in clusters):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
