"""Remote client for Agent Praxis environments.

This client provides the exact same interface as the local Python objects,
but makes HTTP requests to the secure evaluator server.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from agent_praxis.errors import CommandError


class RemoteEnvironment:
    """Generic remote proxy class for any Agent Praxis environment."""

    def __init__(
        self,
        environment_name: str,
        *,
        seed: int | None = None,
        variant: str = "standard",
        base_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self.environment_name = environment_name
        self.variant = variant
        self.base_url = base_url or os.environ.get("EVALUATOR_API_URL", "http://evaluator:8000")
        token = (
            api_token if api_token is not None else os.environ.get("PRAXIS_API_TOKEN", "").strip()
        )
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(base_url=self.base_url, headers=headers)

        resp = self.client.post(
            "/api/setup",
            json={
                "environment_name": environment_name,
                "seed": seed,
                "variant": variant,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        self.session_id = data["session_id"]
        self.seed = data["seed"]
        self.variant = data.get("variant", variant)
        self._description: dict[str, Any] = dict(data["description"])
        self._run_result: dict[str, Any] | None = None

    def description(self) -> dict[str, Any]:
        return self._description

    def action(self, action_name: str, **kwargs: Any) -> Any:
        resp = self.client.post(
            "/api/action",
            json={
                "session_id": self.session_id,
                "action_name": action_name,
                "kwargs": kwargs,
            },
        )
        if resp.status_code == 400:
            raise CommandError(resp.json()["detail"])
        resp.raise_for_status()
        return resp.json()["result"]

    def __getattr__(self, name: str) -> Any:
        def _wrapper(**kwargs: Any) -> Any:
            return self.action(name, **kwargs)

        return _wrapper

    def finalize(self) -> dict[str, Any]:
        resp = self.client.post(
            "/api/evaluate", json={"session_id": self.session_id, "action_name": "finalize"}
        )
        resp.raise_for_status()
        self._run_result = resp.json()
        return self._run_result

    def get_run_result(self) -> dict[str, Any] | None:
        return self._run_result


class RemoteDorianGrayEnvironment(RemoteEnvironment):
    """Specialized remote proxy for Dorian Gray environment."""

    def __init__(
        self,
        *,
        seed: int | None = None,
        variant: str = "standard",
        base_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        super().__init__(
            "dorian-gray",
            seed=seed,
            variant=variant,
            base_url=base_url,
            api_token=api_token,
        )
