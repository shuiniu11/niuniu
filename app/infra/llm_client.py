"""LLM client for interacting with Deepseek via an OpenAI-style API."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.deepseek.com"  # TODO: replace with the actual Deepseek endpoint when available
MODEL_NAME = "deepseek-chat"


class LLMClient:
    """Async client to call the Deepseek LLM for behavior analysis."""

    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url.rstrip("/")

    async def analyze_behavior(self, prompt: str) -> Dict[str, Any]:
        """Call the Deepseek completion API with the provided prompt.

        Raises:
            RuntimeError: When no API key is configured or response parsing fails.
        """

        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")

        url = f"{self.base_url}/v1/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "max_tokens": 512,
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("LLM request failed: %s", exc)
            raise RuntimeError("LLM request failed") from exc

        try:
            data = response.json()
            text = data.get("choices", [{}])[0].get("text", "")
            return json.loads(text)
        except (ValueError, KeyError, IndexError) as exc:
            logger.exception("Failed to parse LLM response: %s", exc)
            raise RuntimeError("Failed to parse LLM response") from exc
