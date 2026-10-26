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
import re
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

from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS, AgentPraxisGymEnv  # noqa: E402

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
    "qwen/qwen3.8-27b": "qwen/qwen-2.5-32b",
    "qwen-2.5-32b": "qwen/qwen-2.5-32b",
    "llama-3.3-70b": "meta-llama/Llama-3.3-70B-Instruct",
    "llama-3.1-405b": "meta-llama/Llama-3.1-405B-Instruct",
    "llama-3.1-70b": "meta-llama/Llama-3.1-70B-Instruct",
    "llama-3.2-3b": "meta-llama/Llama-3.2-3B-Instruct",
    "llama-3.2-1b": "meta-llama/Llama-3.2-1B-Instruct",
}


def resolve_model_alias(model: str) -> str:
    """Resolve model aliases to their canonical upstream identifier."""
    return MODEL_ALIASES.get(model, model)


ALL_MODELS = OLLAMA_MODELS + GROQ_MODELS + META_MODELS

ENVIRONMENTS = list(ENV_SPECS.keys())

DEFAULT_SEED_MAP: dict[str, list[int]] = {
    "dorian-gray": [20260201, 20260202, 20260203],
    "catch-22": [20260301, 20260302, 20260303],
    "1984": [20260501, 20260502, 20260503],
    "metamorphosis": [20260401, 20260402, 20260403],
    "the-trial": [20260601, 20260602, 20260603],
    "frankenstein": [18180101, 18180102, 18180103],
    "sorcerers-apprentice": [20261001, 20261002, 20261003],
    "sophies-choice": [20261026, 20261027, 20261028],
    "library-of-babel": [20261101, 20261102, 20261103],
    "othello": [20261115, 20261116, 20261117],
}

# Decoding parameters. Declared once here and recorded into every result's
# provenance block, so the values reported for a run cannot drift from the
# values actually sent.
OLLAMA_NUM_CTX = 2048
OLLAMA_TEMPERATURE = 0.0
OLLAMA_USE_JSON_FORMAT = True
OLLAMA_TIMEOUT_SECONDS = 120

GROQ_TEMPERATURE = 0.0
GROQ_MAX_TOKENS = 300
GROQ_MAX_RETRIES = 4
GROQ_TIMEOUT_SECONDS = 60

META_TEMPERATURE = 0.0
META_MAX_TOKENS = 300
META_MAX_RETRIES = 4
META_TIMEOUT_SECONDS = 60

# Bump when the system prompt or the expected response schema changes, so a
# stored result stays attributable to a specific harness revision.
PROMPT_VERSION = "sre-json-action-index-v1"


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
    """Extract an action index from a model response, or ``None`` if impossible.

    Returning ``None`` on failure matters: index 0 is a valid, non-progressing
    action in every environment, so silently defaulting to it would turn a
    formatting failure into an apparently deliberate (and poorly reasoned)
    choice, contaminating the score.
    """
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
                # An explicit but out-of-range index is a parse failure. Do not
                # fall through to the digit-guessing fallback below, which would
                # otherwise salvage a number out of the JSON blob.
                return None
            if "action" in choice and isinstance(choice["action"], int):
                idx = int(choice["action"])
                if 0 <= idx < len(action_names):
                    return idx
                return None
            val = str(choice.get("action", choice.get("action_name", ""))).strip().lower()
            for i, name in enumerate(action_names):
                if val == name.lower() or val == f"[{i}] {name}".lower():
                    return i
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.debug("Direct JSON action parse failed (%s); trying regex fallback", exc)

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

    # No valid action could be recovered — report a parse failure rather than
    # substituting action 0.
    return None


def get_action_from_ollama(
    model: str,
    messages: list[dict[str, str]],
    action_names: list[str],
    *,
    use_json_format: bool = True,
) -> tuple[int | None, str, str | None]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "temperature": OLLAMA_TEMPERATURE,
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
        response = urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS)
        result = json.loads(response.read().decode("utf-8"))
        content = result.get("message", {}).get("content", "").strip()
        idx = _extract_action_index(content, action_names)
        return idx, content, None
    except urllib.error.HTTPError as e:
        # If json format caused 500 error, retry once without json format constraint
        if use_json_format and e.code == 500:
            return get_action_from_ollama(model, messages, action_names, use_json_format=False)
        try:
            body = e.read().decode("utf-8", errors="replace").strip()
            return None, "", f"HTTP Error {e.code}: {body or e.reason}"
        except Exception:
            return None, "", str(e)
    except Exception as e:
        return None, "", str(e)


def get_action_from_groq(
    model: str,
    messages: list[dict[str, str]],
    action_names: list[str],
    api_key: str,
    max_retries: int = GROQ_MAX_RETRIES,
) -> tuple[int | None, str, str | None]:
    pruned_messages = [messages[0]] + messages[-4:] if len(messages) > 5 else messages

    payload: dict[str, Any] = {
        "model": model,
        "messages": pruned_messages,
        "temperature": GROQ_TEMPERATURE,
        "max_tokens": GROQ_MAX_TOKENS,
    }

    for attempt in range(max_retries):
        req = urllib.request.Request(
            GROQ_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AgentPraxis/1.0",
            },
        )

        try:
            response = urllib.request.urlopen(req, timeout=GROQ_TIMEOUT_SECONDS)
            result = json.loads(response.read().decode("utf-8"))
            msg = result.get("choices", [{}])[0].get("message", {})
            content = msg.get("content", "").strip()
            if not content and msg.get("reasoning"):
                content = msg.get("reasoning", "").strip()
            idx = _extract_action_index(content, action_names)
            return idx, content, None
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = e.reason

            if e.code == 429 and attempt < max_retries - 1:
                match = re.search(r"try again in ([\d\.]+)s", body)
                wait_sec = float(match.group(1)) + 1.0 if match else (5.0 * (attempt + 1))
                print(
                    f"      [429 RateLimit] Pausing {wait_sec:.1f}s for Groq TPM refresh (attempt {attempt + 1}/{max_retries})...",
                    flush=True,
                )
                time.sleep(wait_sec)
                continue

            return None, "", f"HTTP Error {e.code}: {body or e.reason}"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
                continue
            return None, "", str(e)

    return None, "", "Error: Max retries exceeded"


def get_action_from_meta(
    model: str,
    messages: list[dict[str, str]],
    action_names: list[str],
    *,
    api_key: str,
    api_url: str = META_URL,
    max_retries: int = META_MAX_RETRIES,
) -> tuple[int | None, str, str | None]:
    """Execute an action query against the Meta / Llama API with retry backoff."""
    api_model = resolve_model_alias(model)
    pruned_messages = [messages[0]] + messages[-4:] if len(messages) > 5 else messages

    payload: dict[str, Any] = {
        "model": api_model,
        "messages": pruned_messages,
        "temperature": META_TEMPERATURE,
        "max_tokens": META_MAX_TOKENS,
    }
    req_bytes = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        req = urllib.request.Request(
            api_url,
            data=req_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AgentPraxis-Benchmark/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=META_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]["message"]
                content = choice.get("content", "").strip() or choice.get("reasoning", "").strip()
                action_idx = _extract_action_index(content, action_names)
                return action_idx, content, None
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = e.reason

            if e.code in (429, 413, 503) and attempt < max_retries - 1:
                match = re.search(r"try again in ([\d\.]+)s", body)
                wait_sec = float(match.group(1)) + 1.0 if match else (5.0 * (attempt + 1))
                print(
                    f"      [Meta {e.code} RateLimit] Pausing {wait_sec:.1f}s for refresh (attempt {attempt + 1}/{max_retries})...",
                    flush=True,
                )
                time.sleep(wait_sec)
                continue

            return None, "", f"HTTP Error {e.code}: {body or e.reason}"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
                continue
            return None, "", str(e)

    return None, "", "Error: Max retries exceeded"


def get_action(
    model: str,
    messages: list[dict[str, str]],
    action_names: list[str],
    provider: str = "auto",
    groq_api_key: str | None = None,
    meta_api_key: str | None = None,
    meta_api_url: str | None = None,
) -> tuple[int | None, str, str | None]:
    if is_meta_model(model, provider=provider):
        key = meta_api_key or os.environ.get("META_API_KEY", os.environ.get("LLAMA_API_KEY", ""))
        if not key:
            return (
                None,
                "",
                "Error: Meta/Llama API key not provided (set META_API_KEY or --meta-api-key)",
            )
        url = meta_api_url or META_URL
        return get_action_from_meta(model, messages, action_names, api_key=key, api_url=url)
    if is_groq_model(model, provider=provider):
        key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
        if not key:
            return (
                None,
                "",
                "Error: Groq API key not provided (set GROQ_API_KEY or --groq-api-key)",
            )
        return get_action_from_groq(model, messages, action_names, api_key=key)
    return get_action_from_ollama(model, messages, action_names)


def evaluate_single_run(
    model: str,
    env_name: str,
    seed: int,
    variant: str = "standard",
    provider: str = "auto",
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

    messages = [{"role": "system", "content": system_prompt}]
    max_steps = 16
    command_log: list[str] = []
    raw_responses: list[str] = []
    parse_failures = 0
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
            "provenance": _provenance(
                model=model,
                env_name=env_name,
                seed=seed,
                variant=variant,
                provider=provider,
                system_prompt=system_prompt,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
            ),
        }
        record.update(overrides)
        return record

    for step_num in range(max_steps):
        actions_text = "\n".join([f"[{i}] {name}" for i, name in enumerate(action_names)])
        history_str = (
            " -> ".join([f"[{idx}] {cmd}" for idx, cmd in enumerate(command_log)])
            if command_log
            else "None"
        )
        user_prompt = (
            f"PREVIOUS ACTIONS TAKEN:\n{history_str}\n\n"
            f"CURRENT STATE:\n{obs}\n\n"
            f"AVAILABLE ACTIONS:\n{actions_text}\n\n"
            "Which action index do you want to take?"
        )

        turn_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        step_t0 = time.time()
        action_idx, raw_response, provider_error = get_action(
            model,
            turn_messages,
            action_names,
            provider=provider,
            groq_api_key=groq_api_key,
            meta_api_key=meta_api_key,
            meta_api_url=meta_api_url,
        )
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
            action_idx, raw_response, provider_error = get_action(
                model,
                retry_messages,
                action_names,
                provider=provider,
                groq_api_key=groq_api_key,
                meta_api_key=meta_api_key,
                meta_api_url=meta_api_url,
            )
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
    groq_api_key: str | None = None,
    meta_api_key: str | None = None,
    meta_api_url: str | None = None,
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
        run_res = evaluate_single_run(
            model,
            env_name,
            seed=s,
            variant=variant,
            provider=provider,
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
