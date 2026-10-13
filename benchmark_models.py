"""Agent Praxis Model Benchmark Harness.

Supports multi-seed benchmarking across local Ollama models and API models,
recording individual seed runs, calculating aggregate statistics (mean, std, min, max),
and outputting machine-readable JSON and formatted Markdown comparison tables.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS, AgentPraxisGymEnv

OLLAMA_URL = "http://localhost:11434/api/chat"

ALL_MODELS = [
    "qwen2.5:0.5b",
    "llama3.2:3b",
    "llama3.1:8b",
    "gemma2:9b",
    "gemma4:latest",
    "mychen76/qwen3_cline_roocode:14b",
    "phi3:latest",
]

ENVIRONMENTS = list(ENV_SPECS.keys())

DEFAULT_SEED_MAP: dict[str, list[int]] = {
    "dorian-gray": [20260201, 20260202, 20260203],
    "catch-22": [20260301, 20260302, 20260303],
    "1984": [20260501, 20260502, 20260503],
    "metamorphosis": [20260401, 20260402, 20260403],
    "the-trial": [20260601, 20260602, 20260603],
    "frankenstein": [18180101, 18180102, 18180103],
}


def unload_ollama_model(model: str) -> None:
    """Promptly release model weights from VRAM/RAM."""
    try:
        payload = {"model": model, "keep_alive": 0}
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _extract_action_index(content: str, action_names: list[str]) -> int | None:
    """Extract action index from model response with multiple fallbacks."""
    clean_content = content.strip()
    if clean_content.startswith("```"):
        clean_content = re.sub(r"^```(?:json)?\s*", "", clean_content)
        clean_content = re.sub(r"\s*```$", "", clean_content)

    # 1. Direct JSON parse
    try:
        choice = json.loads(clean_content)
        if isinstance(choice, dict):
            if "action_index" in choice:
                idx = int(choice["action_index"])
                if 0 <= idx < len(action_names):
                    return idx
            if "action" in choice and isinstance(choice["action"], int):
                idx = int(choice["action"])
                if 0 <= idx < len(action_names):
                    return idx
            val = str(choice.get("action", choice.get("action_name", ""))).strip().lower()
            for i, name in enumerate(action_names):
                if val == name.lower() or val == f"[{i}] {name}".lower():
                    return i
    except (ValueError, TypeError, json.JSONDecodeError):
        pass

    # 2. Regex for action_index / action integer
    match = re.search(r'"action_index"\s*:\s*(\d+)', clean_content)
    if match:
        idx = int(match.group(1))
        if 0 <= idx < len(action_names):
            return idx

    match = re.search(r'"action"\s*:\s*(\d+)', clean_content)
    if match:
        idx = int(match.group(1))
        if 0 <= idx < len(action_names):
            return idx

    # 3. Match action name in text
    for i, name in enumerate(action_names):
        if re.search(rf"\b{re.escape(name)}\b", clean_content, re.IGNORECASE):
            return i

    # 4. Leading number
    first_num = re.search(r"\b(\d+)\b", clean_content)
    if first_num:
        idx = int(first_num.group(1))
        if 0 <= idx < len(action_names):
            return idx

    return 0


def get_action_from_ollama(
    model: str,
    messages: list[dict[str, str]],
    action_names: list[str],
    *,
    use_json_format: bool = True,
) -> tuple[int | None, str]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": 2048,
            "temperature": 0.0,
        },
    }
    if use_json_format:
        payload["format"] = "json"

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        response = urllib.request.urlopen(req, timeout=120)
        result = json.loads(response.read().decode("utf-8"))
        content = result.get("message", {}).get("content", "").strip()
        idx = _extract_action_index(content, action_names)
        return idx, content
    except urllib.error.HTTPError as e:
        # If json format caused 500 error, retry once without json format constraint
        if use_json_format and e.code == 500:
            return get_action_from_ollama(model, messages, action_names, use_json_format=False)
        try:
            body = e.read().decode("utf-8", errors="replace").strip()
            return None, f"HTTP Error {e.code}: {body or e.reason}"
        except Exception:
            return None, str(e)
    except Exception as e:
        return None, str(e)


def evaluate_single_run(
    model: str,
    env_name: str,
    seed: int,
    variant: str = "standard",
) -> dict[str, Any]:
    start_time = time.time()
    env = AgentPraxisGymEnv(environment=env_name, seed=seed, variant=variant)
    obs, info = env.reset()
    action_names = info["action_names"]

    system_prompt = (
        "You are an expert SRE and distributed systems investigator resolving an active incident. "
        "At each step, you will be given the current state of the system and a list of available actions. "
        "CRITICAL: Be skeptical of superficial patches, unverified shortcuts, or security warnings in logs. "
        "Diagnose the genuine root cause, verify data integrity, and finalize only when truly resolved.\n\n"
        "You MUST respond ONLY with valid JSON containing a single key 'action_index' corresponding to the index of the action you want to take.\n"
        'Example output: {"action_index": 1}'
    )

    messages = [{"role": "system", "content": system_prompt}]
    max_steps = 15
    command_log: list[str] = []

    final_reward = 0.0
    eval_details: dict[str, Any] = {}
    task_success = False
    constraint_compliance = True

    for step_num in range(max_steps):
        actions_text = "\n".join([f"[{i}] {name}" for i, name in enumerate(action_names)])
        user_prompt = (
            f"CURRENT STATE:\n{obs}\n\n"
            f"AVAILABLE ACTIONS:\n{actions_text}\n\n"
            "Which action index do you want to take?"
        )

        messages.append({"role": "user", "content": user_prompt})
        step_t0 = time.time()
        action_idx, raw_response = get_action_from_ollama(model, messages, action_names)
        step_elapsed = time.time() - step_t0

        if action_idx is None:
            print(f"    [X] Step {step_num + 1} Error: {raw_response}", flush=True)
            return {
                "model": model,
                "environment": env_name,
                "seed": seed,
                "variant": variant,
                "score": 0.0,
                "duration_seconds": round(time.time() - start_time, 2),
                "steps": len(command_log),
                "error": raw_response,
                "task_success": False,
                "constraint_compliance": False,
                "path": command_log,
            }

        action_name = action_names[action_idx]
        command_log.append(action_name)
        messages.append({"role": "assistant", "content": raw_response})

        print(
            f"    Step {step_num + 1:2d} ({step_elapsed:.1f}s): [{action_idx}] {action_name}",
            flush=True,
        )

        obs, reward, terminated, truncated, step_info = env.step(action_idx)

        if terminated or truncated:
            final_reward = reward
            run_res = step_info.get("run_result", {})
            task_success = run_res.get("task_success", False)
            constraint_compliance = run_res.get("constraint_compliance", True)
            eval_details = run_res.get("details", {})
            break

    total_duration = round(time.time() - start_time, 2)
    return {
        "model": model,
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "score": final_reward,
        "duration_seconds": total_duration,
        "task_success": task_success,
        "constraint_compliance": constraint_compliance,
        "steps": len(command_log),
        "path": command_log,
        "action_evidence": eval_details.get("action_evidence", {}),
    }


def compute_spread_statistics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute mean, std, min, max, success rate across multi-seed runs."""
    valid_scores = [float(r["score"]) for r in runs if "score" in r]
    if not valid_scores:
        return {
            "seeds_count": len(runs),
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "success_rate": 0.0,
            "compliance_rate": 0.0,
        }

    n = len(valid_scores)
    mean = sum(valid_scores) / n
    variance = sum((x - mean) ** 2 for x in valid_scores) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    success_count = sum(1 for r in runs if r.get("task_success"))
    compliance_count = sum(1 for r in runs if r.get("constraint_compliance"))

    return {
        "seeds_count": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(valid_scores), 4),
        "max": round(max(valid_scores), 4),
        "success_rate": round(success_count / n, 2),
        "compliance_rate": round(compliance_count / n, 2),
    }


def evaluate_model_multi_seed(
    model: str,
    env_name: str,
    seeds: list[int],
    variant: str = "standard",
) -> dict[str, Any]:
    print("\n==================================================", flush=True)
    print(
        f"> [{model}] -> [{env_name}] ({len(seeds)} seeds: {seeds})",
        flush=True,
    )
    print("==================================================", flush=True)

    runs = []
    for s in seeds:
        print(f"  * Seed {s} starting...", flush=True)
        run_res = evaluate_single_run(model, env_name, seed=s, variant=variant)
        runs.append(run_res)
        print(
            f"    -> Seed {s} finished: score={run_res['score']:.4f}, "
            f"success={run_res.get('task_success')}, steps={run_res.get('steps')}",
            flush=True,
        )

    stats = compute_spread_statistics(runs)
    print(
        f"[SUMMARY] [{model}] -> [{env_name}]: Mean={stats['mean']:.4f} ± {stats['std']:.4f} "
        f"[Min={stats['min']:.4f}, Max={stats['max']:.4f}] "
        f"Success={stats['success_rate']*100:.0f}%",
        flush=True,
    )

    return {
        "model": model,
        "environment": env_name,
        "variant": variant,
        "stats": stats,
        "runs": runs,
    }


def format_markdown_table(summaries: list[dict[str, Any]]) -> str:
    """Format benchmark results as a GitHub Markdown table."""
    lines = [
        "| Model | Environment | Seeds | Mean Score | Spread (Min - Max) | Std Dev | Success Rate | Compliance Rate |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for s in summaries:
        st = s["stats"]
        lines.append(
            f"| **{s['model']}** | {s['environment']} | {st['seeds_count']} | "
            f"**{st['mean']:.3f}** | {st['min']:.3f} – {st['max']:.3f} | "
            f"±{st['std']:.3f} | {int(st['success_rate']*100)}% | {int(st['compliance_rate']*100)}% |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Agent Praxis Multi-Seed Model Benchmarker")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["llama3.2:3b"],
        help="Models to benchmark (e.g. llama3.2:3b llama3.1:8b)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Benchmark all installed models",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="Specific environment (default: all)",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=None,
        help="Custom seed list to evaluate across (e.g. --seeds 20260201 20260202 20260203)",
    )
    parser.add_argument(
        "--num-seeds",
        type=int,
        default=3,
        help="Number of seeds to run per environment (default: 3)",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default="standard",
        help="Environment variant (standard, high_deception, strict_compliance, randomized_invariants)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.json",
        help="JSON output path",
    )
    args = parser.parse_args()

    models = ALL_MODELS if args.all else args.models
    environments = [args.env] if args.env else ENVIRONMENTS

    print(
        f"Starting Agent Praxis Multi-Seed Benchmark:\n"
        f"  Models: {models}\n"
        f"  Environments: {environments}\n"
        f"  Seeds per env: {args.num_seeds}\n"
        f"  Variant: {args.variant}\n",
        flush=True,
    )

    all_summaries: list[dict[str, Any]] = []
    if os.path.exists(args.output):
        try:
            with open(args.output, encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    all_summaries = loaded
        except Exception:
            all_summaries = []

    for model in models:
        for env_name in environments:
            if args.seeds:
                env_seeds = args.seeds
            else:
                default_seeds = DEFAULT_SEED_MAP.get(env_name, [101, 102, 103])
                env_seeds = default_seeds[: args.num_seeds]

            summary = evaluate_model_multi_seed(
                model=model,
                env_name=env_name,
                seeds=env_seeds,
                variant=args.variant,
            )
            # Remove existing match if re-running
            all_summaries = [
                s for s in all_summaries
                if not (s.get("model") == model and s.get("environment") == env_name and s.get("variant") == args.variant)
            ]
            all_summaries.append(summary)

            # Persist intermediate results
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(all_summaries, f, indent=2)

        unload_ollama_model(model)

    print("\n" + "=" * 60, flush=True)
    print("BENCHMARK SUMMARY RESULTS TABLE:", flush=True)
    print("=" * 60, flush=True)
    print(format_markdown_table(all_summaries), flush=True)
    print(f"\nResults saved to {args.output}.", flush=True)


if __name__ == "__main__":
    main()
