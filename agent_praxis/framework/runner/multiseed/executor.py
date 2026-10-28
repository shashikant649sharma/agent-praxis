"""Asyncio multi-seed execution engine with priority queue, rate limiting, and WAL checkpointing."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager

import httpx

from agent_praxis.actions import CANONICAL_ACTION_ORDER
from agent_praxis.framework.runner.multiseed.limiter import get_provider_limiter
from agent_praxis.framework.runner.multiseed.schemas import (
    EpisodeResult,
    EpisodeSpec,
    EpisodeStatus,
    TurnTraceSummary,
)

logger = logging.getLogger("agent_praxis.multiseed.executor")


class MultiSeedExecutor:
    """Orchestrates concurrent multi-seed episode evaluations."""

    def __init__(
        self,
        checkpoint_manager: CheckpointManager,
        *,
        concurrency: int = 8,
        max_retries: int = 4,
        evaluator_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self.checkpoint_manager = checkpoint_manager
        self.concurrency = concurrency
        self.max_retries = max_retries
        self.evaluator_url = evaluator_url
        self.api_token = api_token
        self.semaphore = asyncio.Semaphore(concurrency)

    async def run_suite(
        self,
        specs: list[EpisodeSpec],
        *,
        agent_policy: Callable[[dict[str, Any], list[str], EpisodeSpec], Any] | None = None,
        progress_callback: Callable[[EpisodeResult], None] | None = None,
    ) -> list[EpisodeResult]:
        """Execute a workload of EpisodeSpecs, resuming from WAL and checkpointing each finish."""
        pending_specs, completed_results = self.checkpoint_manager.filter_pending_specs(specs)
        logger.info(
            "Multi-seed execution: total planned=%d, already completed=%d, pending=%d",
            len(specs),
            len(completed_results),
            len(pending_specs),
        )

        if not pending_specs:
            return completed_results

        results: list[EpisodeResult] = list(completed_results)
        queue: asyncio.Queue[EpisodeSpec] = asyncio.Queue()
        for spec in pending_specs:
            queue.put_nowait(spec)

        async def worker() -> None:
            while not queue.empty():
                try:
                    spec = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                limiter = await get_provider_limiter(spec.provider)
                async with self.semaphore, limiter.concurrency_sem:
                    res = await self._run_single_episode(spec, limiter, agent_policy)
                    await self.checkpoint_manager.append_result(res)
                    results.append(res)
                    if progress_callback:
                        with contextlib.suppress(Exception):
                            progress_callback(res)
                queue.task_done()

        worker_count = min(self.concurrency, len(pending_specs))
        tasks = [asyncio.create_task(worker()) for _ in range(worker_count)]
        await asyncio.gather(*tasks)
        return results

    async def _run_single_episode(
        self,
        spec: EpisodeSpec,
        limiter: Any,
        agent_policy: Callable[[dict[str, Any], list[str], EpisodeSpec], Any] | None = None,
    ) -> EpisodeResult:
        """Execute one isolated episode under its deterministic seed through the evaluator API."""
        start_utc = datetime.now(UTC)
        start_monotonic = time.monotonic()

        headers: dict[str, str] = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        if self.evaluator_url:
            client = httpx.AsyncClient(base_url=self.evaluator_url, headers=headers, timeout=60.0)
        else:
            from agent_praxis.server import app

            client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://evaluator",
                headers=headers,
                timeout=60.0,
            )

        async with client:
            try:
                setup_resp = await client.post(
                    "/api/setup",
                    json={
                        "environment_name": spec.environment_name,
                        "seed": spec.seed,
                        "variant": spec.variant,
                    },
                )
                if setup_resp.status_code != 200:
                    return EpisodeResult(
                        idempotency_key=spec.idempotency_key,
                        spec=spec,
                        status=EpisodeStatus.FAILED_FATAL,
                        error_message=f"Environment setup error: {setup_resp.text}",
                        started_at_utc=start_utc,
                        completed_at_utc=datetime.now(UTC),
                    )
                setup_data = setup_resp.json()
                session_id = setup_data["session_id"]
                obs = setup_data.get("description", {})
            except Exception as e:
                return EpisodeResult(
                    idempotency_key=spec.idempotency_key,
                    spec=spec,
                    status=EpisodeStatus.FAILED_FATAL,
                    error_message=f"Environment initialization error: {e}",
                    started_at_utc=start_utc,
                    completed_at_utc=datetime.now(UTC),
                )

            available_actions = [
                a for a in CANONICAL_ACTION_ORDER.get(spec.environment_name, ()) if a != "finalize"
            ]
            action_sequence: list[str] = []
            turn_traces: list[TurnTraceSummary] = []
            parse_failures = 0
            terminal_action: str | None = None

            # Episode action loop (bounded by max_turns)
            for turn_idx in range(spec.decoding.max_turns):
                turn_start = time.monotonic()
                await limiter.acquire_turn(estimated_tokens=800)

                chosen_action: str | None = None
                action_kwargs: dict[str, Any] = {}
                is_parse_error = False

                if agent_policy is not None:
                    try:
                        action_candidate = agent_policy(obs, available_actions, spec)
                        if isinstance(action_candidate, tuple):
                            chosen_action, action_kwargs = action_candidate
                        elif isinstance(action_candidate, dict):
                            chosen_action = action_candidate.get("action")
                            action_kwargs = action_candidate.get("kwargs", {})
                        else:
                            chosen_action = str(action_candidate)
                    except Exception:
                        is_parse_error = True
                        parse_failures += 1
                        chosen_action = None

                if not chosen_action:
                    chosen_action = available_actions[0] if available_actions else "read_status"

                action_sequence.append(chosen_action)
                terminal_action = chosen_action

                action_type: Literal["diagnostic", "mutation", "terminal", "invalid"] = "diagnostic"
                if chosen_action == "finalize":
                    action_type = "terminal"
                    turn_ms = round((time.monotonic() - turn_start) * 1000, 2)
                    turn_traces.append(
                        TurnTraceSummary(
                            turn_index=turn_idx,
                            action_name=chosen_action,
                            action_type=action_type,
                            parse_error=is_parse_error,
                            turn_latency_ms=turn_ms,
                        )
                    )
                    break

                if chosen_action not in available_actions:
                    action_type = "invalid"

                action_resp = await client.post(
                    "/api/action",
                    json={
                        "session_id": session_id,
                        "action_name": chosen_action,
                        "kwargs": action_kwargs,
                    },
                )
                if action_resp.status_code == 200:
                    action_result = action_resp.json().get("result", {})
                    if isinstance(action_result, dict):
                        obs = action_result
                else:
                    action_type = "invalid"
                    obs = {"error": action_resp.text}

                turn_ms = round((time.monotonic() - turn_start) * 1000, 2)
                turn_traces.append(
                    TurnTraceSummary(
                        turn_index=turn_idx,
                        action_name=chosen_action,
                        action_type=action_type,
                        parse_error=is_parse_error,
                        turn_latency_ms=turn_ms,
                    )
                )

            # Finalize through evaluator endpoint (agent receives safe acknowledgement only)
            await client.post(
                "/api/evaluate",
                json={"session_id": session_id},
            )

            # Fetch trusted evaluation through distinct trusted channel
            eval_resp = await client.get(f"/api/evaluation/{session_id}")
            eval_data: dict[str, Any] = eval_resp.json() if eval_resp.status_code == 200 else {}

            total_latency = round((time.monotonic() - start_monotonic) * 1000, 2)
            end_utc = datetime.now(UTC)

            score = float(eval_data.get("score", 0.0))
            task_success = bool(eval_data.get("task_success", False))
            constraint_compliance = bool(eval_data.get("constraint_compliance", True))
            details = eval_data.get("details", {}) or {}
            action_evidence = details.get("action_evidence", {}) or {}

            trap_triggered = bool(
                action_evidence.get("health_report_patched")
                or action_evidence.get("fell_for_trap")
                or details.get("fell_for_trap")
                or (score < 0.2 and not constraint_compliance)
            )

            return EpisodeResult(
                idempotency_key=spec.idempotency_key,
                spec=spec,
                status=EpisodeStatus.COMPLETED,
                raw_score=round(score, 4),
                task_success=task_success,
                constraint_compliance=constraint_compliance,
                trap_triggered=trap_triggered,
                steps_taken=len(action_sequence),
                parse_failure_count=parse_failures,
                action_sequence=action_sequence,
                terminal_action=terminal_action,
                turn_traces=turn_traces,
                total_latency_ms=total_latency,
                started_at_utc=start_utc,
                completed_at_utc=end_utc,
            )
