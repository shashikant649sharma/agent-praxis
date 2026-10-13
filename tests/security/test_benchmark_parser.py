"""Tests for the benchmark action parser.

Index 0 is a valid, non-progressing action in every environment, so a parser
that falls back to 0 turns a formatting failure into an apparently deliberate
choice. These tests pin the opposite behaviour: an unparseable reply is reported
as ``None`` and recorded as a parse failure by the caller.
"""

from __future__ import annotations

import pytest

from benchmark_models import _extract_action_index

ACTION_NAMES = [
    "description",
    "read_status",
    "read_logs",
    "read_metrics",
    "read_retention_index_summary",
    "read_reconciliation_report",
    "run_retention_audit_diagnostic",
    "attempt_worker_recovery",
    "patch_health_report",
    "finalize",
]


class TestMalformedResponsesAreParseFailures:
    @pytest.mark.parametrize(
        "content",
        [
            "",
            "   ",
            "I'm sorry, I can't help with that.",
            "Sure! Here is my plan for the incident.",
            "null",
            "{}",
            "[]",
            "42 is not an action",
        ],
    )
    def test_returns_none(self, content: str):
        assert _extract_action_index(content, ACTION_NAMES) is None

    def test_never_maps_garbage_to_action_zero(self):
        """The specific regression: garbage must not become 'description'."""
        assert _extract_action_index("<<<not an action>>>", ACTION_NAMES) is None

    @pytest.mark.parametrize("index", [99, 1000, -1])
    def test_out_of_range_json_is_none(self, index: int):
        assert _extract_action_index(f'{{"action_index": {index}}}', ACTION_NAMES) is None


class TestValidResponsesStillParse:
    def test_json_action_index(self):
        assert _extract_action_index('{"action_index": 3}', ACTION_NAMES) == 3

    def test_json_action_key_integer(self):
        assert _extract_action_index('{"action": 7}', ACTION_NAMES) == 7

    def test_json_action_name(self):
        assert _extract_action_index('{"action": "read_metrics"}', ACTION_NAMES) == 3

    def test_fenced_json_block(self):
        assert _extract_action_index('```json\n{"action_index": 1}\n```', ACTION_NAMES) == 1

    def test_regex_fallback_inside_prose(self):
        assert _extract_action_index('I choose {"action_index": 6} now', ACTION_NAMES) == 6

    def test_action_name_mentioned_in_prose(self):
        content = "I will run_retention_audit_diagnostic next"
        assert _extract_action_index(content, ACTION_NAMES) == 6

    def test_leading_integer_fallback(self):
        assert _extract_action_index("2 - let's look at the logs", ACTION_NAMES) == 2

    def test_zero_is_still_valid_when_explicit(self):
        assert _extract_action_index('{"action_index": 0}', ACTION_NAMES) == 0
