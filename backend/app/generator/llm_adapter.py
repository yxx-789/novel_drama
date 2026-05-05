# llm_adapter.py
# -*- coding: utf-8 -*-
"""
异步 LLM Adapter，使用 httpx 进行 OpenAI-Compatible API 调用
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class AsyncLLMAdapter:
    async def invoke(self, prompt: str) -> str:
        raise NotImplementedError("Subclasses must implement .invoke(prompt) method.")


class OpenAICompatibleAdapter(AsyncLLMAdapter):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = 600,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def invoke(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.replace("```", "").strip()


def create_llm_adapter(
    interface_format: str,
    base_url: str,
    model_name: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: int = 600,
) -> AsyncLLMAdapter:
    fmt = interface_format.strip().lower()
    if fmt in ("openai", "deepseek", "ollama", "siliconflow", "volcanoengine"):
        return OpenAICompatibleAdapter(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    raise ValueError(f"Unsupported interface_format: {interface_format}")
