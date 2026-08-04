"""Defensive MCP Streamable-HTTP client for xiaohongshu-mcp（同步版）。"""
import json
import threading
import time
from typing import Any

import requests


class McpClient:
    def __init__(self, url: str, timeout: int = 180, max_retries: int = 2, request_interval: float = 0.8):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = max(0.0, request_interval)
        self._session = requests.Session()
        self._session_id: str | None = None
        self._req_id = 0
        self._last_request_at = 0.0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _throttle(self) -> None:
        remaining = self.request_interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def _post(self, payload: dict, expect_body: bool = True) -> dict:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        for attempt in range(self.max_retries + 1):
            try:
                self._throttle()
                resp = self._session.post(self.url, headers=headers, json=payload, timeout=self.timeout)
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                if not self._session_id:
                    self._session_id = resp.headers.get("Mcp-Session-Id")
                if not expect_body:
                    return {}
                ct = resp.headers.get("content-type", "")
                if "text/event-stream" in ct:
                    for line in resp.text.splitlines():
                        if line.startswith("data:"):
                            raw = line[5:].strip()
                            if raw and raw != "[DONE]":
                                return json.loads(raw)
                    return {}
                return resp.json() if resp.content else {}
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError(f"MCP request failed: {exc}") from exc
                time.sleep(1.5 * (2**attempt))

    def connect(self) -> None:
        body = self._post({
            "jsonrpc": "2.0", "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "novel-drama-collector", "version": "1.0.0"}},
            "id": self._next_id(),
        })
        if body.get("error"):
            raise RuntimeError(f"MCP initialize error: {body['error']}")
        if not self._session_id:
            raise RuntimeError("MCP initialize did not return Mcp-Session-Id")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, expect_body=False)

    def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        body = self._post({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
            "id": self._next_id(),
        })
        if body.get("error"):
            raise RuntimeError(f"Tool {name} RPC error: {body['error']}")
        result = body.get("result") or {}
        text = "\n".join(
            item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"
        )
        if result.get("isError"):
            raise RuntimeError(f"Tool {name} error: {text}")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    def close(self) -> None:
        self._session.close()
