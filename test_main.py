import json
import threading
import time
import urllib.error
import urllib.request

from main import RequestHandler, detect_cluster, run_server
from http.server import HTTPServer


def _start_server():
    server = HTTPServer(("127.0.0.1", 0), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def _post_json(port: int, path: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(request)


def test_detect_cluster_logic():
    result = detect_cluster(["bot001", "bot002", "userA", "bot003", "userA"])
    assert result["overall_risk_level"] in {"low", "medium", "high"}
    assert result["summary"]["total_users"] == 5.0
    assert any(cluster["label"].startswith("prefix:bot") for cluster in result["clusters"])


def test_http_endpoint_returns_cluster_data():
    server, port = _start_server()
    time.sleep(0.05)
    try:
        response = _post_json(port, "/api/detect_cluster", {"user_ids": ["a", "a", "b"]})
        body = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert body["summary"]["duplicate_ratio"] > 0
    finally:
        server.shutdown()
        server.server_close()


def test_http_endpoint_handles_invalid_body():
    server, port = _start_server()
    time.sleep(0.05)
    try:
        response = _post_json(port, "/api/detect_cluster", {"user_ids": []})
    except urllib.error.HTTPError as exc:
        assert exc.code == 400
    else:
        server.shutdown()
        server.server_close()
        assert False, "Expected HTTP 400 for empty user_ids"
    finally:
        server.shutdown()
        server.server_close()
