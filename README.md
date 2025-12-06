# 反水军风险识别服务

基于 FastAPI 的“反水军”风险识别服务，包含用户行为分析和水军集群检测两类接口。集群检测基于用户评论行为、IP 重合度、AI 文本特征等结构化信号构建相似图并提取可疑组件。

## 环境准备

1. Python 版本：`3.10+`
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 设置环境变量 `DEEPSEEK_API_KEY`（请勿将真实密钥提交到仓库）：

```bash
cp .env.example .env
# 编辑 .env 将其中的占位符替换为真实密钥
export DEEPSEEK_API_KEY="your_deepseek_api_key"
```

## 启动服务

```bash
uvicorn app.main:app --reload
```

服务启动后，主要接口位于 `/api/*`，健康检查为 `/health`。

## 接口示例

### 1. 用户行为分析 `/api/analyze_behavior`

请求示例：

```json
{
  "user_id": "12345",
  "comments": [
    "这产品太棒了，强烈推荐！！！",
    "这产品太棒了，强烈推荐！！！"
  ],
  "ip_history": ["1.2.3.4", "1.2.3.4"],
  "device_ids": ["dev_a", "dev_a"],
  "extra": {
    "register_time": "2025-12-01T12:00:00Z",
    "last_login_time": "2025-12-06T01:00:00Z",
    "comments_last_24h": 100
  }
}
```

响应示例：

```json
{
  "user_id": "12345",
  "risk_score": 0.87,
  "risk_level": "high",
  "suspicious_factors": [
    "短时间内大量重复评论",
    "与>50个账号共享相同IP"
  ],
  "advice": "建议加入人工复核队列"
}
```

### 2. 水军集群检测 `/api/detect_cluster`

请求示例：

```json
{
  "user_ids": ["u1", "u2", "u3", "u4", "u5"]
}
```

响应示例：

```json
{
  "clusters": [
    {
      "cluster_id": "c1",
      "user_ids": ["u1", "u2", "u3"],
      "size": 3,
      "avg_similarity": 0.85,
      "shared_ip_ratio": 0.9,
      "shared_device_ratio": 0.8,
      "risk_score": 0.92,
      "risk_level": "high",
      "description": "该集群用户在相同时间段内发布高度相似的营销评论，并大量共享相同IP和设备。"
    }
  ],
  "overall_risk_level": "high"
}
```

以上示例与实际输出可能略有差异，集群检测目前为简化实现，未来可接入真实聚类与相似度计算逻辑。
