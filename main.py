import json
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Tuple


def _compute_prefix(user_id: str, length: int = 3) -> str:
    return user_id if len(user_id) < length else user_id[:length]


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _build_clusters(user_ids: List[str]) -> List[Dict[str, object]]:
    prefix_map: Dict[str, List[str]] = defaultdict(list)
    for user_id in user_ids:
        prefix_map[_compute_prefix(user_id)].append(user_id)

    clusters: List[Dict[str, object]] = []
    total_users = len(user_ids)

    for prefix, members in prefix_map.items():
        if len(members) < 2:
            continue

        duplicate_hits = sum(count - 1 for count in Counter(members).values() if count > 1)
        duplicate_ratio = duplicate_hits / len(members)
        shared_prefix_ratio = len(members) / total_users
        risk_score = round(0.6 * duplicate_ratio + 0.4 * shared_prefix_ratio, 3)

        clusters.append(
            {
                "label": f"prefix:{prefix}",
                "members": members,
                "size": len(members),
                "risk_score": risk_score,
                "signals": {
                    "duplicate_ratio": round(duplicate_ratio, 3),
                    "shared_prefix_ratio": round(shared_prefix_ratio, 3),
                },
            }
        )

    return sorted(clusters, key=lambda c: c["risk_score"], reverse=True)


def _compute_summary(user_ids: List[str]) -> Dict[str, float]:
    total = len(user_ids)
    if total == 0:
        return {"total_users": 0.0, "unique_users": 0.0, "duplicate_ratio": 0.0}

    duplicates = Counter(user_ids)
    duplicate_hits = sum(count - 1 for count in duplicates.values() if count > 1)
    duplicate_ratio = duplicate_hits / total

    return {
        "total_users": float(total),
        "unique_users": float(len(duplicates)),
        "duplicate_ratio": round(duplicate_ratio, 3),
    }


def detect_cluster(user_ids: List[str]) -> Dict[str, object]:
    normalized = [user_id.strip() for user_id in user_ids if user_id and user_id.strip()]
    if not normalized:
        raise ValueError("user_ids cannot be empty")

    clusters = _build_clusters(normalized)
    summary = _compute_summary(normalized)
    highest_score = clusters[0]["risk_score"] if clusters else summary.get("duplicate_ratio", 0.0)

    return {
        "overall_risk_level": _risk_level(highest_score),
        "summary": summary,
        "clusters": clusters,
    }


def _parse_json(body: bytes) -> Tuple[bool, object]:
    try:
        return True, json.loads(body.decode("utf-8"))
    except Exception:
        return False, {"error": "invalid JSON"}


class RequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Dict[str, object]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802 (http server signature)
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 (http server signature)
        if self.path != "/api/detect_cluster":
            self._send_json(404, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        ok, payload = _parse_json(body)
        if not ok:
            self._send_json(400, payload)
            return

        user_ids = payload.get("user_ids") if isinstance(payload, dict) else None
        if not isinstance(user_ids, list):
            self._send_json(400, {"error": "user_ids must be a list"})
            return

        try:
            result = detect_cluster(user_ids)
        except ValueError as exc:  # validation errors
            self._send_json(400, {"error": str(exc)})
            return

        self._send_json(200, result)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    httpd = HTTPServer((host, port), RequestHandler)
    print(f"Starting server on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
