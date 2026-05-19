"""Convert MCP tool definitions into Anthropic tool-use schema.

MCP returns: { name, description, inputSchema: { type:'object', properties:{}, ... } }
Anthropic expects: { name, description, input_schema: { type:'object', properties:{}, ... } }
"""
from typing import Any, Dict, Iterable, List


def _safe_schema(schema: Any) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    out = dict(schema)
    out.setdefault("type", "object")
    out.setdefault("properties", {})
    return out


def normalize_tools(mcp_tools: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for t in mcp_tools:
        if not isinstance(t, dict) or "name" not in t:
            continue
        normalized.append({
            "name":         t["name"],
            "description":  (t.get("description") or "")[:1024],
            "input_schema": _safe_schema(t.get("inputSchema") or t.get("input_schema")),
        })
    return normalized


def filter_tools(tools: List[Dict[str, Any]], names: Iterable[str]) -> List[Dict[str, Any]]:
    keep = set(names)
    return [t for t in tools if t["name"] in keep]
