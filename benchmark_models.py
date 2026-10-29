"""Agent Praxis Model Benchmark Harness.

Supports multi-seed benchmarking across local Ollama models and API models,
recording individual seed runs, calculating aggregate statistics (mean, std, min, max),
and outputting machine-readable JSON and formatted Markdown comparison tables.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("agent_praxis.benchmark")

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Auto-load .env if present
if os.path.exists(".env"):
    with contextlib.suppress(Exception), open(".env", encoding="utf-8") as _env_f:
        for _env_line in _env_f:
            _env_line = _env_line.strip()
            if _env_line and not _env_line.startswith("#") and "=" in _env_line:
                _env_k, _env_v = _env_line.split("=", 1)
                if _env_k.strip() not in os.environ:
                    os.environ[_env_k.strip()] = _env_v.strip()

from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS, AgentPraxisGymEnv  # noqa: E402
from agent_praxis.framework.prompt import (  # noqa: E402
    DEFAULT_CONTEXT_POLICY,
    PROMPT_VERSION,
    PROVIDER_DEFAULT_CONTEXT_LIMITS,
    SUPPORTED_CONTEXT_POLICIES,
    ModelTurnResponse,
    apply_context_budget,
    extract_action_with_status,
    query_provider_action,
    render_turn_prompt,
)

OLLAMA_URL = "http://localhost:11434/api/chat"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
META_URL = os.environ.get(
    "META_API_URL",
    os.environ.get("LLAMA_API_URL", "https://api.llama-api.com/chat/completions"),
)

OLLAMA_MODELS = [
    "qwen2.5:0.5b",
    "llama3.2:3b",
    "llama3.1:8b",
    "gemma2:9b",
    "gemma4:latest",
    "mychen76/qwen3_cline_roocode:14b",
    "phi3:latest",
]

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen-2.5-32b",
    "qwen/qwen3.8-27b",  # Retained as legacy benchmark identifier alias
    "openai/gpt-oss-20b",
    "allam-2-7b",
]

META_MODELS = [
    "meta/muse-spark-open",
    "meta-models/Muse-Spark-Open-816B-A42B",
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Llama-3.1-405B-Instruct",
    "meta-llama/Llama-3.1-70B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Llama-3.2-1B-Instruct",
]

MODEL_ALIASES: dict[str, str] = {
    "muse-spark-open": "meta/muse-spark-open",
    "muse-spark": "meta/muse-spark-open",
    "meta-models/Muse-Spark-Open-816B-A42B": "meta/muse-spark-open",
    "qwen-2.5-32b": "qwen/qwen-2.5-32b",
    "llama-3.3-70b": "meta-llama/Llama-3.3-70B-Instruct",
    "llama-3.1-405b": "meta-llama/Llama-3.1-405B-Instruct",
    "llama-3.1-70b": "meta-llama/Llama-3.1-70B-Instruct",
    "llama-3.2-3b": "meta-llama/Llama-3.2-3B-Instruct",
    "llama-3.2-1b": "meta-llama/Llama-3.2-1B-Instruct",
}


def resolve_model_alias(model: str) -> str:
    """Resolve model aliases to their canonical upstream identifier."""
    canonical = MODEL_ALIASES.get(model)
    if canonical is not None and canonical != model:
        logger.warning(
            "Model identifier '%s' is a legacy alias; resolving to canonical '%s'",
            model,
            canonical,
        )
        return canonical
    return model


ALL_MODELS = OLLAMA_MODELS + GROQ_MODELS + META_MODELS

ENVIRONMENTS = list(ENV_SPECS.keys())

DEFAULT_SEED_MAP: dict[str, list[int]] = {
    "dorian-gray": [20260201, 20260202, 20260203, 20260204, 20260205],
    "catch-22": [20260301, 20260302, 20260303, 20260304, 20260305],
    "1984": [20260501, 20260502, 20260503, 20260504, 20260505],
    "metamorphosis": [20260401, 20260402, 20260403, 20260404, 20260405],
    "the-trial": [20260601, 20260602, 20260603, 20260604, 20260605],
    "frankenstein": [18180101, 18180102, 18180103, 18180104, 18180105],
    "sorcerers-apprentice": [20261001, 20261002, 20261003, 20261004, 20261005],
    "sophies-choice": [20261026, 20261027, 20261028, 20261029, 20261030],
    "library-of-babel": [20261101, 20261102, 20261103, 20261104, 20261105],
    "othello": [20261115, 20261116, 20261117, 20261118, 20261119],
}

# Decoding parameters. Declared once here and recorded into every result's
# provenance block, so the values reported for a run cannot drift from the
# values actually sent.
OLLAMA_NUM_CTX = 2048
OLLAMA_TEMPERATURE = 0.0
OLLAMA_USE_JSON_FORMAT = True
OLLAMA_TIMEOUT_SECONDS = 120

GROQ_TEMPERATURE = 0.0
GROQ_MAX_TOKENS = 1024
GROQ_MAX_RETRIES = 4
GROQ_TIMEOUT_SECONDS = 60

META_TEMPERATURE = 0.0
META_MAX_TOKENS = 300
META_MAX_RETRIES = 4
META_TIMEOUT_SECONDS = 60


def apply_context_policy(
    messages: list[dict[str, str]],
    policy: str = DEFAULT_CONTEXT_POLICY,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Apply unified token-budgeted context management across model providers."""
    return apply_context_budget(messages, policy=policy)


def _repo_commit_sha() -> str:
    """Best-effort git revision for provenance. Never raises."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        logger.debug("Failed to resolve git revision: %s", exc)
        return "unknown"
    sha = completed.stdout.strip()
    return sha if completed.returncode == 0 and sha else "unknown"


def is_meta_model(model: str, provider: str = "auto") -> bool:
    """Determine whether a model should be routed to Meta."""
    if provider == "meta":
        return True
    if provider in ("groq", "ollama"):
        return False
    resolved = resolve_model_alias(model)
    return (
        model in META_MODELS
        or resolved in META_MODELS
        or model.startswith("meta-llama/")
        or model.startswith("meta-models/")
        or model.startswith("meta/")
        or "muse" in model.lower()
    )


def is_groq_model(model: str, provider: str = "auto") -> bool:
    """Determine whether a model should be routed to Groq."""
    if provider == "groq":
        return True
    if provider in ("ollama", "meta"):
        return False
    if is_meta_model(model, provider=provider):
        return False
    resolved = resolve_model_alias(model)
    return model in GROQ_MODELS or resolved in GROQ_MODELS or "/" in model


def _effective_provider(model: str, provider: str = "auto") -> str:
    """Which backend a model identifier will actually be routed to."""
    if is_meta_model(model, provider=provider):
        return "meta"
    if is_groq_model(model, provider=provider):
        return "groq"
    return "ollama"


def _provenance(
    *,
    model: str,
    env_name: str,
    seed: int,
    variant: str,
    provider: str,
    system_prompt: str,
    started_at: str,
    finished_at: str,
    context_policy: str = DEFAULT_CONTEXT_POLICY,
) -> dict[str, Any]:
    """Everything needed to attribute and reproduce a single run."""
    return {
        "repo_commit": _repo_commit_sha(),
        "model": model,
        "canonical_model": resolve_model_alias(model),
        "provider": _effective_provider(model, provider),
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
        "context_policy": context_policy,
        "decoding": {
            "ollama": {
                "num_ctx": OLLAMA_NUM_CTX,
                "temperature": OLLAMA_TEMPERATURE,
                "json_format": OLLAMA_USE_JSON_FORMAT,
            },
            "groq": {
                "temperature": GROQ_TEMPERATURE,
                "max_tokens": GROQ_MAX_TOKENS,
            },
            "meta": {
                "temperature": META_TEMPERATURE,
                "max_tokens": META_MAX_TOKENS,
            },
        },
        "started_at": started_at,
        "finished_at": finished_at,
    }


def unload_ollama_model(model: str) -> None:
    """Promptly release model weights from VRAM/RAM (Ollama only)."""
    if is_groq_model(model) or is_meta_model(model):
        return
    try:
        payload = {"model": model, "keep_alive": 0}
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        logger.debug("Failed to unload Ollama model %s: %s", model, exc)


def _extract_action_index(content: str, action_names: list[str]) -> int | None:
    """Extract an action index from a model response, or None if impossible."""
    idx, status = extract_action_with_status(content, action_names)
    if status in ("out_of_range", "invalid_action_name", "parse_failure"):
        return None
    return idx


def get_action(
    model: str,
    messages: list[dict[str, str]],
    action_names: list[str],
    provider: str = "auto",
    context_policy: str = DEFAULT_CONTEXT_POLICY,
    groq_api_key: str | None = None,
    meta_api_key: str | None = None,
    meta_api_url: str | None = None,
) -> ModelTurnResponse:
    """Execute action query with unified token budgeting and truthful outcome classification."""
    return query_provider_action(
        model=model,
        messages=messages,
        action_names=action_names,
        provider=provider,
        context_policy=context_policy,
        groq_api_key=groq_api_key,
        meta_api_key=meta_api_key,
        meta_api_url=meta_api_url,
    )


def evaluate_single_run(
    model: str,
    env_name: str,
    seed: int,
    variant: str = "standard",
    provider: str = "auto",
    context_policy: str = DEFAULT_CONTEXT_POLICY,
    groq_api_key: str | None = None,
    meta_api_key: str | None = None,
    meta_api_url: str | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    env = AgentPraxisGymEnv(environment=env_name, seed=seed, variant=variant)
    obs, info = env.reset()
    action_names = info["action_names"]

    system_prompt = (
        "You are an expert SRE and distributed systems investigator resolving an active incident. "
        "At each step, you will be given the current state of the system and a list of available actions. "
        "Diagnose the root cause from evidence, take necessary remedial actions, and call finalize when resolved.\n\n"
        "You MUST respond ONLY with valid JSON containing a single key 'action_index' corresponding to the index of the action you want to take.\n"
        'Example output: {"action_index": 1}'
    )

    action_history: list[tuple[int, str]] = []
    max_steps = 16
    command_log: list[str] = []
    raw_responses: list[str] = []
    parse_failures = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    tokens_measured = False
    last_truncation_provenance: dict[str, Any] = {}
    started_at = datetime.now(UTC).isoformat()

    final_reward = 0.0
    eval_details: dict[str, Any] = {}
    task_success = False
    constraint_compliance = True

    def _result(**overrides: Any) -> dict[str, Any]:
        """Build a result record; every record carries provenance."""
        record: dict[str, Any] = {
            "model": model,
            "environment": env_name,
            "seed": seed,
            "variant": variant,
            "score": 0.0,
            "steps": len(command_log),
            "path": list(command_log),
            "raw_responses": list(raw_responses),
            "parse_failures": parse_failures,
            "task_success": False,
            "constraint_compliance": False,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "tokens_measured": tokens_measured,
            "truncation_provenance": last_truncation_provenance,
            "provenance": _provenance(
                model=model,
                env_name=env_name,
                seed=seed,
                variant=variant,
                provider=provider,
                system_prompt=system_prompt,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                context_policy=context_policy,
            ),
        }
        record.update(overrides)
        return record

    eff_provider = _effective_provider(model, provider)
    limits = PROVIDER_DEFAULT_CONTEXT_LIMITS.get(
        eff_provider, PROVIDER_DEFAULT_CONTEXT_LIMITS["default"]
    )

    for step_num in range(max_steps):
        # 1. Build canonical prompt (System instructions -> Available actions -> Observation -> Action history -> Decision request)
        prompt_res = render_turn_prompt(
            system_prompt=system_prompt,
            action_names=action_names,
            obs=obs,
            action_history=action_history,
            context_policy=context_policy,
            limits=limits,
        )
        last_truncation_provenance = prompt_res.provenance

        if prompt_res.context_overflow:
            error_kind, error_message = (
                "context_overflow",
                "Mandatory prompt content exceeded context budget",
            )
            print(f"    [X] Step {step_num + 1} {error_kind}: {error_message}", flush=True)
            return _result(
                duration_seconds=round(time.time() - start_time, 2),
                error=error_message,
                error_kind=error_kind,
            )

        turn_messages = prompt_res.messages
        step_t0 = time.time()
        turn_resp = get_action(
            model,
            turn_messages,
            action_names,
            provider=provider,
            context_policy=context_policy,
            groq_api_key=groq_api_key,
            meta_api_key=meta_api_key,
            meta_api_url=meta_api_url,
        )
        action_idx, raw_response, provider_error = turn_resp
        total_prompt_tokens += turn_resp.token_usage.prompt_tokens
        total_completion_tokens += turn_resp.token_usage.completion_tokens
        tokens_measured = tokens_measured or turn_resp.token_usage.is_measured

        if raw_response:
            raw_responses.append(raw_response)

        if action_idx is None and provider_error is None:
            # The model replied, but nothing in the reply mapped to an action.
            # Retry exactly once with an explicit format correction; the
            # observation itself is unchanged.
            print(
                f"    [!] Step {step_num + 1} unparseable response; retrying with a format hint",
                flush=True,
            )
            parse_failures += 1
            retry_messages = [
                *turn_messages,
                {"role": "assistant", "content": raw_response},
                {
                    "role": "user",
                    "content": (
                        "Your previous reply could not be parsed as an action. Respond with "
                        'ONLY a JSON object of the form {"action_index": <integer>} and nothing else.'
                    ),
                },
            ]
            retry_resp = get_action(
                model,
                retry_messages,
                action_names,
                provider=provider,
                context_policy=context_policy,
                groq_api_key=groq_api_key,
                meta_api_key=meta_api_key,
                meta_api_url=meta_api_url,
            )
            action_idx, raw_response, provider_error = retry_resp
            total_prompt_tokens += retry_resp.token_usage.prompt_tokens
            total_completion_tokens += retry_resp.token_usage.completion_tokens
            tokens_measured = tokens_measured or retry_resp.token_usage.is_measured
            if raw_response:
                raw_responses.append(raw_response)

        step_elapsed = time.time() - step_t0

        if provider_error is not None or action_idx is None:
            if provider_error is not None:
                error_kind, error_message = "provider_error", provider_error
            else:
                error_kind, error_message = "parse_failure", "unparseable model response"
            print(f"    [X] Step {step_num + 1} {error_kind}: {error_message}", flush=True)
            return _result(
                duration_seconds=round(time.time() - start_time, 2),
                error=error_message,
                error_kind=error_kind,
            )

        if action_idx < 0 or action_idx >= len(action_names):
            error_kind, error_message = "invalid_action", f"Invalid action index {action_idx}"
            print(f"    [X] Step {step_num + 1} {error_kind}: {error_message}", flush=True)
            return _result(
                duration_seconds=round(time.time() - start_time, 2),
                error=error_message,
                error_kind=error_kind,
            )

        action_name = action_names[action_idx]
        command_log.append(action_name)
        action_history.append((action_idx, action_name))

        print(
            f"    Step {step_num + 1:2d} ({step_elapsed:.1f}s): [{action_idx}] {action_name}",
            flush=True,
        )

        obs, reward, terminated, truncated, step_info = env.step(action_idx)

        if terminated or truncated:
            final_reward = reward
            if hasattr(env, "get_evaluation_result"):
                eval_obj = env.get_evaluation_result()
            else:
                eval_obj = step_info.get("run_result", {})

            if hasattr(eval_obj, "task_success"):
                task_success = bool(eval_obj.task_success)
                constraint_compliance = bool(eval_obj.constraint_compliance)
                eval_details = getattr(eval_obj, "details", {})
            elif isinstance(eval_obj, dict):
                task_success = bool(eval_obj.get("task_success", False))
                constraint_compliance = bool(eval_obj.get("constraint_compliance", True))
                eval_details = eval_obj.get("details", {})
            else:
                task_success = False
                constraint_compliance = True
                eval_details = {}
            break

    total_duration = round(time.time() - start_time, 2)
    return _result(
        score=final_reward,
        duration_seconds=total_duration,
        task_success=task_success,
        constraint_compliance=constraint_compliance,
        action_evidence=eval_details.get("action_evidence", {}),
        scoring_breakdown=eval_details.get("scoring_breakdown", {}),
    )


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
            "parse_failures": 0,
            "parse_failure_rate": 0.0,
        }

    n = len(valid_scores)
    mean = sum(valid_scores) / n
    variance = sum((x - mean) ** 2 for x in valid_scores) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    success_count = sum(1 for r in runs if r.get("task_success"))
    compliance_count = sum(1 for r in runs if r.get("constraint_compliance"))
    # Reported separately from task success so a formatting failure is never
    # silently attributed to poor reasoning.
    parse_failures = sum(int(r.get("parse_failures", 0) or 0) for r in runs)
    runs_with_parse_failure = sum(1 for r in runs if int(r.get("parse_failures", 0) or 0) > 0)

    return {
        "seeds_count": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(valid_scores), 4),
        "max": round(max(valid_scores), 4),
        "success_rate": round(success_count / n, 2),
        "compliance_rate": round(compliance_count / n, 2),
        "parse_failures": parse_failures,
        "parse_failure_rate": round(runs_with_parse_failure / n, 2),
    }


def evaluate_model_multi_seed(
    model: str,
    env_name: str,
    seeds: list[int],
    variant: str = "standard",
    provider: str = "auto",
    context_policy: str = DEFAULT_CONTEXT_POLICY,
    groq_api_key: str | None = None,
    meta_api_key: str | None = None,
    meta_api_url: str | None = None,
) -> dict[str, Any]:
    print("\n==================================================", flush=True)
    print(
        f"> [{model}] -> [{env_name}] ({len(seeds)} seeds: {seeds}, context={context_policy})",
        flush=True,
    )
    print("==================================================", flush=True)

    runs = []
    for s in seeds:
        print(f"  * Seed {s} starting...", flush=True)
        run_res = evaluate_single_run(
            model,
            env_name,
            seed=s,
            variant=variant,
            provider=provider,
            context_policy=context_policy,
            groq_api_key=groq_api_key,
            meta_api_key=meta_api_key,
            meta_api_url=meta_api_url,
        )
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
        f"Success={stats['success_rate'] * 100:.0f}%",
        flush=True,
    )

    return {
        "model": model,
        "environment": env_name,
        "variant": variant,
        "seeds": list(seeds),
        "context_policy": context_policy,
        "stats": stats,
        "runs": runs,
    }


def format_markdown_table(summaries: list[dict[str, Any]]) -> str:
    """Format benchmark results as a GitHub Markdown table."""
    lines = [
        "| Model | Environment | Seeds | Mean Score | Spread (Min - Max) | Std Dev | Success Rate | Compliance Rate | Parse-Fail Rate |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for s in summaries:
        st = s["stats"]
        lines.append(
            f"| **{s['model']}** | {s['environment']} | {st['seeds_count']} | "
            f"**{st['mean']:.3f}** | {st['min']:.3f} – {st['max']:.3f} | "
            f"±{st['std']:.3f} | {int(st['success_rate'] * 100)}% | {int(st['compliance_rate'] * 100)}% | "
            f"{int(float(st.get('parse_failure_rate', 0.0)) * 100)}% |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Agent Praxis Multi-Seed Model Benchmarker")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["llama3.2:3b"],
        help="Models to benchmark (e.g. llama3.2:3b llama3.1:8b openai/gpt-oss-120b)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Benchmark all installed models",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "ollama", "groq", "meta"],
        default="auto",
        help="Inference provider (auto, ollama, groq, meta)",
    )
    parser.add_argument(
        "--context-policy",
        choices=list(SUPPORTED_CONTEXT_POLICIES),
        default=DEFAULT_CONTEXT_POLICY,
        help="Context management policy across LLM provider turns (default: full_history)",
    )
    parser.add_argument(
        "--groq-api-key",
        type=str,
        default=None,
        help="Groq API key (defaults to GROQ_API_KEY environment variable)",
    )
    parser.add_argument(
        "--meta-api-key",
        type=str,
        default=None,
        help="Meta/Llama API key (defaults to META_API_KEY or LLAMA_API_KEY environment variable)",
    )
    parser.add_argument(
        "--meta-api-url",
        type=str,
        default=None,
        help="Meta/Llama API URL (defaults to META_API_URL or LLAMA_API_URL environment variable)",
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
    groq_api_key = args.groq_api_key or os.environ.get("GROQ_API_KEY")
    meta_api_key = args.meta_api_key or os.environ.get(
        "META_API_KEY", os.environ.get("LLAMA_API_KEY")
    )
    meta_api_url = args.meta_api_url or META_URL

    print(
        f"Starting Agent Praxis Multi-Seed Benchmark:\n"
        f"  Models: {models}\n"
        f"  Environments: {environments}\n"
        f"  Provider: {args.provider}\n"
        f"  Context policy: {args.context_policy}\n"
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
                provider=args.provider,
                context_policy=args.context_policy,
                groq_api_key=groq_api_key,
                meta_api_key=meta_api_key,
                meta_api_url=meta_api_url,
            )
            # Remove existing match if re-running
            all_summaries = [
                s
                for s in all_summaries
                if not (
                    s.get("model") == model
                    and s.get("environment") == env_name
                    and s.get("variant") == args.variant
                )
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
