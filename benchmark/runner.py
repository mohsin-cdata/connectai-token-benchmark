"""Run scenarios against the Anthropic API as full multi-turn loops.

The runner drives Claude through `anthropic.messages.create`, inspects the
response for `tool_use` blocks, dispatches every tool call (via a caller-
supplied dispatcher) back into the loop as a `tool_result`, and repeats
until `end_turn` or a per-scenario turn cap.

Token usage is summed across every turn -- that sum is what the locked
numbers in LOCKED_RESULTS.py report. Without multi-turn, scenarios that
walk a discovery chain (Raw baseline, Derived Views without hint, etc.)
would dramatically under-report.

The dispatcher is `tool_dispatcher(tool_name, tool_input) -> str`. The
caller (run_benchmark.py) decides what to do per tool: route to live MCP,
return a synthetic payload, or error.
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import anthropic

import config

# Per-scenario default turn caps. Raw baseline gets 10 because the discovery
# chain takes several turns; everything else stops within 6.
DEFAULT_MAX_TURNS  = 6
BASELINE_MAX_TURNS = 10
MAX_TOOL_RESULT_CHARS = 8000


@dataclass
class ScenarioResult:
    name:                  str
    brief_section:         str
    summary:               str
    note:                  Optional[str] = None
    input_tokens:          int = 0
    output_tokens:         int = 0
    total_tokens:          int = 0
    tool_calls:            int = 0
    stop_reason:           Optional[str] = None
    runs:                  int = 0
    inferences:            List[Dict[str, Any]] = field(default_factory=list)
    error:                 Optional[str] = None
    static_only:           bool = False
    baseline_input_tokens: Optional[int] = None


class Runner:
    def __init__(self, api_key: str, model: str = config.MODEL):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    # -- token-count helpers (unchanged) --------------------------------------

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

    # -- multi-turn loop ------------------------------------------------------

    def _messages_create_with_retry(self, **kwargs):
        """Retry on RateLimitError honoring the Retry-After header."""
        while True:
            try:
                return self.client.messages.create(**kwargs)
            except anthropic.RateLimitError as e:
                try:
                    retry_after = int(e.response.headers.get("retry-after", "30"))
                except Exception:
                    retry_after = 30
                wait = retry_after + 5
                print(f"      rate-limited; sleeping {wait}s...")
                time.sleep(wait)

    def fire_multiturn(self, system: str, tools: List[Dict[str, Any]],
                       messages: List[Dict[str, Any]],
                       tool_dispatcher: Optional[Callable[[str, Dict[str, Any]], str]] = None,
                       max_turns: int = DEFAULT_MAX_TURNS) -> Dict[str, Any]:
        """Drive one full multi-turn loop for a single scenario run.

        Returns one dict with summed token counts, total tool calls across
        all turns, the final stop_reason, and wall-clock time.
        """
        msgs = [dict(m) for m in messages]
        cin = cout = tool_calls = 0
        last_stop: Optional[str] = None
        t_start = time.perf_counter()
        ts = time.time()

        for _turn in range(max_turns):
            kwargs: Dict[str, Any] = {
                "model":       self.model,
                "system":      system,
                "messages":    msgs,
                "max_tokens":  config.INFERENCE_MAX_TOKENS,
                "temperature": config.INFERENCE_TEMPERATURE,
            }
            if tools:
                kwargs["tools"] = tools

            resp = self._messages_create_with_retry(**kwargs)
            cin  += int(resp.usage.input_tokens)
            cout += int(resp.usage.output_tokens)
            last_stop = resp.stop_reason

            tool_uses = [b for b in resp.content
                         if getattr(b, "type", None) == "tool_use"]
            if not tool_uses or last_stop == "end_turn":
                break

            msgs.append({"role": "assistant", "content": resp.content})
            tool_calls += len(tool_uses)

            tool_results = []
            for tu in tool_uses:
                try:
                    body = tool_dispatcher(tu.name, dict(tu.input)) if tool_dispatcher \
                        else f"ERROR: no dispatcher configured for {tu.name}"
                except Exception as e:
                    body = json.dumps({"error": f"{type(e).__name__}: {e}"})
                if not isinstance(body, str):
                    body = json.dumps(body, default=str)
                if len(body) > MAX_TOOL_RESULT_CHARS:
                    body = body[:MAX_TOOL_RESULT_CHARS] + " ...[truncated]"
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tu.id,
                    "content":     body,
                })
            msgs.append({"role": "user", "content": tool_results})

        return {
            "ts":            ts,
            "input_tokens":  cin,
            "output_tokens": cout,
            "total_tokens":  cin + cout,
            "tool_calls":    tool_calls,
            "stop_reason":   last_stop,
            "wall_s":        time.perf_counter() - t_start,
        }

    # -- scenario orchestration ----------------------------------------------

    def run_scenario(self, scenario: Dict[str, Any], runs: int, full: bool,
                     tool_dispatcher: Optional[Callable[[str, Dict[str, Any]], str]] = None
                     ) -> ScenarioResult:
        result = ScenarioResult(
            name=scenario["name"],
            brief_section=scenario["brief_section"],
            summary=scenario["summary"],
            note=scenario.get("note"),
            static_only=scenario.get("static_only", False),
        )
        try:
            # Static-only scenarios: count input tokens vs a baseline tool set.
            # No inference, no multi-turn -- just the input-cost delta.
            if scenario.get("static_only"):
                opt_in  = self.count_input_tokens(
                    scenario["system"], scenario["tools"], scenario["messages"])
                base_in = self.count_input_tokens(
                    scenario["system"], scenario["_baseline_tools"], scenario["messages"])
                result.input_tokens          = opt_in
                result.baseline_input_tokens = base_in
                result.total_tokens          = opt_in
                result.runs                  = 1
                return result

            # Pre-fire input-only count (single count_tokens call).
            in_only = self.count_input_tokens(
                scenario["system"], scenario["tools"], scenario["messages"])
            result.input_tokens = in_only
            result.total_tokens = in_only

            if not full:
                result.runs = 1
                return result

            # Full mode: real multi-turn execution.
            max_turns = BASELINE_MAX_TURNS if scenario["name"] == "Raw baseline" else DEFAULT_MAX_TURNS
            ins, outs, tots, calls, stops = [], [], [], [], []
            for _ in range(runs):
                r = self.fire_multiturn(
                    scenario["system"], scenario["tools"], scenario["messages"],
                    tool_dispatcher=tool_dispatcher, max_turns=max_turns,
                )
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
            result.stop_reason   = stops[0] if stops else None
            result.runs          = runs
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
        return result
