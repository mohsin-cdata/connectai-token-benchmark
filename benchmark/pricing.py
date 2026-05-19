"""Cost math anchored to Sonnet 4.6 list price (May 2026)."""
from typing import Dict

import config


def cost_per_query(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens  * config.PRICING["input_per_mtok"]  / 1_000_000
        + output_tokens * config.PRICING["output_per_mtok"] / 1_000_000
    )


def saving_per_query(baseline_in: int, baseline_out: int,
                     opt_in: int, opt_out: int) -> float:
    return cost_per_query(baseline_in, baseline_out) - cost_per_query(opt_in, opt_out)


def monthly_savings(per_query_saving: float, volumes=None) -> Dict[int, float]:
    volumes = volumes or config.PROJECTION_VOLUMES
    return {v: per_query_saving * v for v in volumes}


def reduction_pct(baseline: int, optimized: int) -> float:
    if baseline <= 0:
        return 0.0
    return (baseline - optimized) / baseline * 100.0
