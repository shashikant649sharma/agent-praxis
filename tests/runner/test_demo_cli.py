"""Tests for Agent Praxis demo command and CLI entrypoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

from agent_praxis.__main__ import main as main_entrypoint
from agent_praxis.commands.demo import (
    VERIFIED_CANONICAL_SUMMARY,
    format_live_comparison_table,
    format_side_by_side_table,
    load_canonical_summary,
    run_live_policy,
)
from agent_praxis.commands.demo import (
    main as demo_main,
)


def test_load_canonical_summary_returns_all_environments() -> None:
    summary = load_canonical_summary()
    assert len(summary) == 10
    assert "1984" in summary
    assert "catch-22" in summary
    for _env, pols in summary.items():
        assert pols["noop"] == 0.0
        assert pols["read_only"] == 0.0
        assert pols["blind_search"] == 0.0
        assert pols["oracle"] == 1.0


def test_format_side_by_side_table_ascii_and_markdown() -> None:
    ascii_table = format_side_by_side_table(VERIFIED_CANONICAL_SUMMARY, as_markdown=False)
    assert "Agent Praxis Policy Ladder Baseline Sweep" in ascii_table
    assert "1984" in ascii_table
    assert "0.0000" in ascii_table

    md_table = format_side_by_side_table(VERIFIED_CANONICAL_SUMMARY, as_markdown=True)
    assert "| Environment |" in md_table
    assert "| `1984` |" in md_table


def test_run_live_policy_execution() -> None:
    noop = run_live_policy("1984", "noop", seed=42)
    assert noop["score"] == 0.0
    assert noop["task_success"] is False

    ro = run_live_policy("1984", "read_only", seed=42)
    assert ro["score"] == 0.0
    assert ro["task_success"] is False

    orc = run_live_policy("1984", "oracle", seed=42)
    assert orc["score"] == 1.0
    assert orc["task_success"] is True


def test_format_live_comparison_table() -> None:
    results = [
        run_live_policy("1984", "noop", seed=42),
        run_live_policy("1984", "oracle", seed=42),
    ]
    txt = format_live_comparison_table(results, as_markdown=False)
    assert "noop" in txt
    assert "oracle" in txt
    assert "1.0000" in txt

    md = format_live_comparison_table(results, as_markdown=True)
    assert "| `noop` |" in md
    assert "| `oracle` |" in md


def test_demo_main_cli_summary(capsys: pytest.CaptureFixture[str]) -> None:
    ret = demo_main([])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "Policy Ladder Baseline Sweep" in captured
    assert "1984" in captured


def test_demo_main_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    ret = demo_main(["--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data: dict[str, Any] = json.loads(captured)
    assert "1984" in data
    assert data["1984"]["oracle"] == 1.0


def test_demo_main_cli_live(capsys: pytest.CaptureFixture[str]) -> None:
    ret = demo_main(["--live", "--env", "1984", "--seed", "42"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "Live Policy Execution Demo on '1984'" in captured
    assert "oracle" in captured


def test_praxis_main_entrypoint_demo(capsys: pytest.CaptureFixture[str]) -> None:
    ret = main_entrypoint(["demo", "--markdown"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "| Environment |" in captured
    assert "| `catch-22` |" in captured
