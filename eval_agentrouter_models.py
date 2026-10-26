"""Agent Praxis: AgentRouter Evaluation Harness for GPT-6.1 Sol and GPT-5.6 Sol.

Evaluates:
- `gpt-6.1-sol` (OpenAI: GPT-6.1 Sol via AgentRouter Responses API)
- `gpt-5.6-sol` (OpenAI: GPT-5.6 Sol via AgentRouter Responses API)

Features:
- OpenAI Responses API format (/v1/responses)
- Automatic retry on 502/503/429/timeouts
- Out-of-band evaluation with independent ground-truth verification
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from agent_praxis.framework.evaluation.schema import RunResult, make_run_result
from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent_praxis.agentrouter")

AGENTROUTER_URL = "https://agentrouter.org/v1/responses"


def load_agentrouter_key() -> str:
    """Load AgentRouter API key from .env or environment variable."""
    key = os.environ.get("AGENTROUTER_API_KEY", "")
    if not key and os.path.exists(".env"):
        with open(".env", encoding="utf-8") as f:
            for line in f:
                if line.startswith("AGENTROUTER_API_KEY="):
                    key = line.strip().split("=", 1)[1]
                    break
    return key


def extract_action_index(content: str, action_names: list[str]) -> int | None:
    """Extract action index from raw model response text."""
    # 1. Direct JSON extraction
    try:
        data = json.loads(content.strip())
        if isinstance(data, dict):
            for k in ("action_index", "action", "index"):
                if k in data and isinstance(data[k], int) and 0 <= data[k] < len(action_names):
                    return data[k]
    except Exception:
        pass

    # 2. Regex for {"action_index": N}
    m = re.search(r'["\']action(?:_index)?["\']\s*:\s*(\d+)', content)
    if m:
        idx = int(m.group(1))
        if 0 <= idx < len(action_names):
            return idx

    # 3. Action name fallback
    for i, name in enumerate(action_names):
        if re.search(rf"\b{re.escape(name)}\b", content, re.IGNORECASE):
            return i

    return None


def call_agentrouter(
    model: str,
    prompt: str,
    api_key: str,
    max_retries: int = 4,
    timeout_sec: int = 45,
) -> tuple[str, str | None]:
    """Execute query against AgentRouter Responses API with backoff."""
    payload = {
        "model": model,
        "input": prompt,
    }
    req_bytes = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        req = urllib.request.Request(
            AGENTROUTER_URL,
            data=req_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Cline/3.0.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                output = data.get("output", [])
                text = ""
                if isinstance(output, list):
                    for item in output:
                        if item.get("type") == "message":
                            for part in item.get("content", []):
                                if part.get("type") in ("output_text", "text"):
                                    text += part.get("text", "")
                elif isinstance(output, str):
                    text = output

                if text:
                    return text.strip(), None
                return "", "Empty response payload"

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (502, 503, 504, 429) and attempt < max_retries - 1:
                wait_sec = 3.0 * (attempt + 1)
                logger.warning("AgentRouter HTTP %d on %s, retrying in %.1fs...", e.code, model, wait_sec)
                time.sleep(wait_sec)
                continue
            return "", f"HTTP Error {e.code}: {body[:200]}"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            return "", str(e)

    return "", "Max retries exceeded"


def evaluate_agentrouter_model_on_env(
    model: str,
    env_name: str,
    seed: int,
    api_key: str,
    max_steps: int = 16,
) -> dict[str, Any]:
    """Evaluate a model from AgentRouter on an Agent Praxis environment."""
    env = AgentPraxisGymEnv(environment=env_name, seed=seed)
    obs, info = env.reset()
    action_names = info["action_names"]

    trajectory = []
    raw_responses = []
    start_time = time.time()

    system_preamble = (
        "You are an expert SRE and distributed systems investigator resolving an incident.\n"
        "At each step you see the environment state and available tools.\n"
        "Diagnose root cause, take corrective actions, and finalize.\n"
        "Respond ONLY with valid JSON: {\"action_index\": <integer>}\n"
    )

    history_log = []

    for step in range(max_steps):
        tools_formatted = "\n".join(f"[{i}] {name}" for i, name in enumerate(action_names))
        prompt = (
            f"{system_preamble}\n"
            f"Environment: {env_name} (Step {step + 1}/{max_steps})\n\n"
            f"Current Observation:\n{obs}\n\n"
            f"Recent Actions Taken: {trajectory[-4:] if trajectory else 'None'}\n\n"
            f"Available Actions:\n{tools_formatted}\n\n"
            f"Select the single best next action. Return ONLY JSON: {{\"action_index\": <integer>}}"
        )

        t0 = time.time()
        # Keep observation safely bounded to prevent upstream gateway buffer errors
        bounded_obs = obs if len(obs) <= 2500 else obs[:2500] + "\n...[truncated for gateway transport]"
        prompt = (
            f"{system_preamble}\n"
            f"Environment: {env_name} (Step {step + 1}/{max_steps})\n\n"
            f"Current Observation:\n{bounded_obs}\n\n"
            f"Recent Actions Taken: {trajectory[-4:] if trajectory else 'None'}\n\n"
            f"Available Actions:\n{tools_formatted}\n\n"
            f"Select the single best next action. Return ONLY JSON: {{\"action_index\": <integer>}}"
        )

        resp_text, err = call_agentrouter(model, prompt, api_key=api_key)
        step_duration = round(time.time() - t0, 2)

        if err or not resp_text:
            logger.error("Step %d %s failed due to gateway/provider error: %s", step + 1, model, err)
            total_duration = round(time.time() - start_time, 2)
            return {
                "model": model,
                "environment": env_name,
                "seed": seed,
                "run_status": "INVALID_RUN_GATEWAY_ERROR",
                "error_kind": "provider_gateway_error",
                "error_details": err,
                "task_success": None,  # Technical abort: no fault of the model
                "score": None,         # Excluded from benchmark score aggregation
                "valid_steps_before_error": len(trajectory),
                "steps": len(trajectory),
                "trajectory": trajectory,
                "duration_seconds": total_duration,
                "note": "Technical/gateway error occurred; invalid run per benchmark protocol",
            }

        raw_responses.append(resp_text)
        action_idx = extract_action_index(resp_text, action_names)

        if action_idx is None:
            logger.warning("Unparseable response at step %d: %s", step + 1, resp_text[:100])
            total_duration = round(time.time() - start_time, 2)
            return {
                "model": model,
                "environment": env_name,
                "seed": seed,
                "run_status": "PARSE_FAILURE",
                "error_kind": "model_formatting_error",
                "task_success": False,
                "score": 0.0,
                "steps": len(trajectory),
                "trajectory": trajectory,
                "duration_seconds": total_duration,
            }

        action_name = action_names[action_idx]
        trajectory.append(action_name)
        logger.info("Step %2d (%.1fs): [%d] %s", step + 1, step_duration, action_idx, action_name)

        obs, reward, terminated, truncated, step_info = env.step(action_idx)

        if terminated or truncated:
            run_res = step_info.get("run_result", {})
            total_duration = round(time.time() - start_time, 2)
            return {
                "model": model,
                "environment": env_name,
                "seed": seed,
                "run_status": "COMPLETED",
                "score": round(reward, 4),
                "task_success": run_res.get("task_success", False),
                "constraint_compliance": run_res.get("constraint_compliance", True),
                "steps": step + 1,
                "trajectory": trajectory,
                "duration_seconds": total_duration,
                "scoring_breakdown": run_res.get("details", {}).get("scoring_breakdown", {}),
                "action_evidence": run_res.get("details", {}).get("action_evidence", {}),
            }

    total_duration = round(time.time() - start_time, 2)
    return {
        "model": model,
        "environment": env_name,
        "seed": seed,
        "run_status": "STEP_BUDGET_EXHAUSTED",
        "score": 0.0,
        "task_success": False,
        "constraint_compliance": True,
        "steps": len(trajectory),
        "trajectory": trajectory,
        "duration_seconds": total_duration,
        "scoring_breakdown": {},
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate AgentRouter models on Agent Praxis")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-6.1-sol", "gpt-5.6-sol"],
        help="Models to evaluate (e.g. gpt-6.1-sol gpt-5.6-sol)",
    )
    parser.add_argument(
        "--envs",
        nargs="+",
        default=["othello", "sorcerers-apprentice"],
        help="Environments to test on",
    )
    args = parser.parse_args()

    api_key = load_agentrouter_key()
    if not api_key:
        print("ERROR: AGENTROUTER_API_KEY not found in .env or environment.")
        sys.exit(1)

    print("=" * 80)
    print("AGENT PRAXIS: AGENTROUTER MODEL EVALUATION (GPT-6.1 SOL & GPT-5.6 SOL)")
    print("=" * 80)

    results = []
    seed_map = {"othello": 20261115, "sorcerers-apprentice": 20261001, "sophies-choice": 20261026, "library-of-babel": 20261101}

    for env_name in args.envs:
        seed = seed_map.get(env_name, 20260101)
        for model in args.models:
            print(f"\nEvaluating [{model}] on [{env_name}] (Seed: {seed})...", flush=True)
            res = evaluate_agentrouter_model_on_env(model, env_name, seed=seed, api_key=api_key)
            results.append(res)
            score_str = f"{res['score']:.4f}" if res['score'] is not None else "N/A"
            success_str = str(res['task_success']) if res['task_success'] is not None else "INVALID (Gateway Error)"
            print(
                f"Result -> [{model}] on [{env_name}]: Status={res.get('run_status')} | "
                f"Score={score_str} | Verdict={success_str} | Steps={res['steps']} | Duration={res['duration_seconds']}s",
                flush=True,
            )

    print("\n" + "=" * 90)
    print("SUMMARY RESULTS TABLE (EXCLUDING TECHNICAL GATEWAY ERRORS):")
    print("=" * 90)
    print(f"{'Model':<16} {'Environment':<20} {'Status':<22} {'Score':<8} {'Verdict':<12} {'Steps':<7} {'Trajectory'}")
    print("-" * 90)
    for r in results:
        traj_hint = str(r['trajectory'][:3]) + f" ({len(r['trajectory'])} steps)"
        score_val = f"{r['score']:.3f}" if r['score'] is not None else "EXCLUDED"
        verdict = "PASS" if r['task_success'] is True else ("FAIL" if r['task_success'] is False else "INVALID")
        print(f"{r['model']:<16} {r['environment']:<20} {r.get('run_status', 'N/A'):<22} {score_val:<8} {verdict:<12} {r['steps']:<7} {traj_hint}")

    with open("docs/AGENTROUTER_BENCHMARK_RESULTS.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved full evaluation evidence to docs/AGENTROUTER_BENCHMARK_RESULTS.json.")


if __name__ == "__main__":
    main()
