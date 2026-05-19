"""Run scenarios through the Anthropic API: count_tokens + (optional) messages."""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import anthropic

import config


@dataclass
class ScenarioResult:
    name:           str
    brief_section:  str
    summary:        str
    note:           Optional[str] = None
    input_tokens:   int = 0
    output_tokens:  int = 0
    total_tokens:   int = 0
    tool_calls:     int = 0
    stop_reason:    Optional[str] = None
    runs:           int = 0
    inferences:     List[Dict[str, Any]] = field(default_factory=list)
    error:          Optional[str] = None
    static_only:    bool = False
    baseline_input_tokens: Optional[int] = None


class Runner:
    def __init__(self, api_key: str, model: str = config.MODEL):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def count_input_tokens(self, system: str, tools: List[Dict[str, Any]],
                           messages: List[Dict[str, Any]]) -> int:
        kwargs: Dict[str, Any] = {
            "model":    self.model,
            "system":   system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        resp = self.client.messages.count_tokens(**kwargs)
        return int(resp.input_tokens)

    def fire_inference(self, system: str, tools: List[Dict[str, Any]],
                       messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model":       self.model,
            "system":      system,
            "messages":    messages,
            "max_tokens":  config.INFERENCE_MAX_TOKENS,
            "temperature": config.INFERENCE_TEMPERATURE,
        }
        if tools:
            kwargs["tools"] = tools
        t0 = time.perf_counter()
        resp = self.client.messages.create(**kwargs)
        wall_s = time.perf_counter() - t0
        usage = resp.usage
        tool_use_blocks = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        return {
            "ts":            time.time(),
            "input_tokens":  int(usage.input_tokens),
            "output_tokens": int(usage.output_tokens),
            "total_tokens":  int(usage.input_tokens) + int(usage.output_tokens),
            "tool_calls":    len(tool_use_blocks),
            "stop_reason":   resp.stop_reason,
            "wall_s":        wall_s,
        }

    def run_scenario(self, scenario: Dict[str, Any], runs: int, full: bool) -> ScenarioResult:
        result = ScenarioResult(
            name=scenario["name"],
            brief_section=scenario["brief_section"],
            summary=scenario["summary"],
            note=scenario.get("note"),
            static_only=scenario.get("static_only", False),
        )
        try:
            if scenario.get("static_only"):
                opt_in = self.count_input_tokens(scenario["system"], scenario["tools"], scenario["messages"])
                base_in = self.count_input_tokens(
                    scenario["system"], scenario["_baseline_tools"], scenario["messages"]
                )
                result.input_tokens          = opt_in
                result.baseline_input_tokens = base_in
                result.total_tokens          = opt_in
                result.runs                  = 1
                return result

            in_only = self.count_input_tokens(
                scenario["system"], scenario["tools"], scenario["messages"]
            )
            result.input_tokens = in_only
            result.total_tokens = in_only

            if not full:
                result.runs = 1
                return result

            ins, outs, tots, calls, stops = [], [], [], [], []
            for _ in range(runs):
                r = self.fire_inference(scenario["system"], scenario["tools"], scenario["messages"])
                ins.append(r["input_tokens"])
                outs.append(r["output_tokens"])
                tots.append(r["total_tokens"])
                calls.append(r["tool_calls"])
                stops.append(r["stop_reason"])
                result.inferences.append(r)
            result.input_tokens  = int(round(statistics.mean(ins)))
            result.output_tokens = int(round(statistics.mean(outs)))
            result.total_tokens  = int(round(statistics.mean(tots)))
            result.tool_calls    = int(round(statistics.mean(calls)))
            result.stop_reason   = stops[0]
            result.runs          = runs
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
        return result
