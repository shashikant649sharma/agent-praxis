"""Agent Praxis framework environment sub-package — loads canonical contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "framework" / "environment" / "contract.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.environment.contract_canonical",
    str(_CANONICAL),
)
_contract = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _contract
_spec.loader.exec_module(_contract)

contract = _contract

__all__ = ["contract"]
