"""FastAPI server for isolated evaluator execution.

This server exposes the environment actions over HTTP, ensuring that the
agent runs in a completely separate process (or container) from the evaluator.
The agent cannot access the evaluator's memory, ground truth, or source code.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent_praxis.environments import (
    catch_22_env,
    dorian_gray_env,
    metamorphosis_env,
    nineteen_eighty_four_env,
    the_trial_env,
)
from agent_praxis.framework.evaluation.schema import make_run_result

app = FastAPI(title="Agent Praxis Evaluator API")

_ENV_FACTORIES: dict[str, Any] = {
    "dorian-gray": dorian_gray_env.DorianGrayEnvironment,
    "catch-22": catch_22_env.Catch22Environment,
    "1984": nineteen_eighty_four_env.NineteenEightyFourEnvironment,
    "metamorphosis": metamorphosis_env.MetamorphosisEnvironment,
    "the-trial": the_trial_env.TheTrialEnvironment,
}

_active_environments: dict[str, Any] = {}
_session_env_names: dict[str, str] = {}


class SetupRequest(BaseModel):
    environment_name: str
    seed: int | None = None


class ActionRequest(BaseModel):
    session_id: str
    action_name: str
    kwargs: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/setup")
def setup_environment(req: SetupRequest) -> dict[str, Any]:
    if req.environment_name not in _ENV_FACTORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported environment: {req.environment_name}. Available: {list(_ENV_FACTORIES.keys())}",
        )

    session_id = str(uuid.uuid4())
    factory = _ENV_FACTORIES[req.environment_name]
    env = factory(seed=req.seed)
    _active_environments[session_id] = env
    _session_env_names[session_id] = req.environment_name

    return {
        "session_id": session_id,
        "environment_name": req.environment_name,
        "seed": env.seed,
        "description": env.description(),
    }


@app.post("/api/action")
def execute_action(req: ActionRequest) -> dict[str, Any]:
    env = _active_environments.get(req.session_id)
    if not env:
        raise HTTPException(status_code=404, detail="Invalid session ID")

    try:
        method = getattr(env, req.action_name)
    except AttributeError:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action_name}") from None

    try:
        result = method(**req.kwargs) if req.kwargs else method()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/evaluate")
def evaluate(req: ActionRequest) -> dict[str, Any]:
    """Finalize and evaluate the session, returning the graded score."""
    import contextlib

    env = _active_environments.get(req.session_id)
    if not env:
        raise HTTPException(status_code=404, detail="Invalid session ID")

    env_name = _session_env_names.get(req.session_id, "unknown")

    with contextlib.suppress(Exception):
        env.finalize()

    snap = env.snapshot_for_evaluation()
    run_result = make_run_result(
        snap,
        environment_name=env_name,
        command_log=snap.get("command_log", []),
    )

    if req.session_id in _active_environments:
        del _active_environments[req.session_id]
    if req.session_id in _session_env_names:
        del _session_env_names[req.session_id]

    return run_result.to_dict()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
