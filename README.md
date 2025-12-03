# 水军集群检测示例服务

使用纯 Python 标准库实现的简单 HTTP 服务，提供 `/api/detect_cluster` 接口，在不依赖数据库的情况下检测用户 ID 列表是否存在可疑集群。

## 快速开始

```bash
python main.py
```

默认在 `http://0.0.0.0:8000` 启动。接口说明：
- `GET /health`：健康检查
- `POST /api/detect_cluster`：检测用户 ID 列表，Body 形如 `{ "user_ids": ["bot001", "userA"] }`

## 示例请求

```bash
curl -X POST http://localhost:8000/api/detect_cluster \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["bot001", "bot002", "userA", "bot003", "userA"]}'
```

返回示例：

```json
{
  "overall_risk_level": "high",
  "summary": {
    "total_users": 5.0,
    "unique_users": 4.0,
    "duplicate_ratio": 0.2
  },
  "clusters": [
    {
      "label": "prefix:bot",
      "members": ["bot001", "bot002", "bot003"],
      "size": 3,
      "risk_score": 0.6,
      "signals": {
        "duplicate_ratio": 0.0,
        "shared_prefix_ratio": 0.6
      }
    }
  ]
}
```

## 测试

```bash
pytest
```

测试无需额外依赖，使用标准库启动临时服务器并验证接口返回。
