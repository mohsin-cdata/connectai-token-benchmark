"""SSE-aware MCP JSON-RPC client for Connect AI."""
import base64
import json
import uuid
from typing import Any, Dict, List, Optional

import requests


class MCPError(RuntimeError):
    pass


class MCPClient:
    def __init__(self, base_url: str, email: str, access_token: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        creds = base64.b64encode(f"{email}:{access_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.timeout = timeout

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        resp = requests.post(
            self.base_url, headers=self.headers,
            data=json.dumps(payload), timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise MCPError(f"MCP {method} HTTP {resp.status_code}: {resp.text[:300]}")

        body = resp.text
        if "text/event-stream" in resp.headers.get("Content-Type", "") or body.lstrip().startswith("event:") or "data:" in body:
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        return json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
            raise MCPError(f"MCP {method}: no data: line in SSE body")

        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise MCPError(f"MCP {method}: invalid JSON ({e}); body[:200]={body[:200]}")

    def initialize(self) -> Dict[str, Any]:
        return self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "connectai-token-benchmark", "version": "0.1.0"},
        })

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._rpc("tools/list", {})
        if "error" in result:
            raise MCPError(f"tools/list error: {result['error']}")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if "error" in result:
            raise MCPError(f"tools/call {name} error: {result['error']}")
        return result.get("result", {})
