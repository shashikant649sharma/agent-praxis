"""Remote client for Agent Praxis environments.

This client provides the exact same interface as the local Python objects,
but makes HTTP requests to the secure evaluator server.
"""

from __future__ import annotations

import contextlib
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
        timeout: float = 30.0,
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
        self.client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout)

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
        if name.startswith("_"):
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

        def _wrapper(**kwargs: Any) -> Any:
            return self.action(name, **kwargs)

        return _wrapper

    def finalize(self, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"session_id": self.session_id, "action_name": "finalize"}
        if kwargs:
            payload["kwargs"] = kwargs
        resp = self.client.post("/api/evaluate", json=payload)
        resp.raise_for_status()
        self._run_result = resp.json()
        return self._run_result

    def get_run_result(self) -> dict[str, Any] | None:
        return self._run_result

    def close(self) -> None:
        if self._run_result is None and hasattr(self, "session_id") and self.session_id:
            with contextlib.suppress(Exception):
                self.client.delete(f"/api/session/{self.session_id}")
        self.client.close()

    def __enter__(self) -> RemoteEnvironment:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


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


class AsyncRemoteEnvironment:
    """Asynchronous remote proxy class for Agent Praxis environments."""

    def __init__(
        self,
        environment_name: str,
        *,
        seed: int | None = None,
        variant: str = "standard",
        base_url: str | None = None,
        api_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.environment_name = environment_name
        self.variant = variant
        self.seed = seed
        self.base_url = base_url or os.environ.get("EVALUATOR_API_URL", "http://evaluator:8000")
        token = (
            api_token if api_token is not None else os.environ.get("PRAXIS_API_TOKEN", "").strip()
        )
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=timeout)
        self.session_id: str | None = None
        self._description: dict[str, Any] = {}
        self._run_result: dict[str, Any] | None = None
        self._closed = False

    async def setup(self) -> AsyncRemoteEnvironment:
        resp = await self.client.post(
            "/api/setup",
            json={
                "environment_name": self.environment_name,
                "seed": self.seed,
                "variant": self.variant,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self.session_id = data["session_id"]
        self.seed = data["seed"]
        self.variant = data.get("variant", self.variant)
        self._description = dict(data["description"])
        return self

    async def description(self) -> dict[str, Any]:
        return self._description

    async def action(self, action_name: str, **kwargs: Any) -> Any:
        if not self.session_id:
            raise RuntimeError(
                "Environment session not setup. Call await env.setup() or use async with."
            )
        resp = await self.client.post(
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

    async def finalize(self, **kwargs: Any) -> dict[str, Any]:
        if not self.session_id:
            raise RuntimeError("Environment session not setup.")
        payload: dict[str, Any] = {"session_id": self.session_id, "action_name": "finalize"}
        if kwargs:
            payload["kwargs"] = kwargs
        resp = await self.client.post("/api/evaluate", json=payload)
        resp.raise_for_status()
        self._run_result = resp.json()
        return self._run_result

    def get_run_result(self) -> dict[str, Any] | None:
        return self._run_result

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.session_id and self._run_result is None:
            with contextlib.suppress(Exception):
                await self.client.delete(f"/api/session/{self.session_id}")
        await self.client.aclose()

    async def __aenter__(self) -> AsyncRemoteEnvironment:
        await self.setup()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
