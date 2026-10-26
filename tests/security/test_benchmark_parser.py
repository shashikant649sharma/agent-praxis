"""Tests for the benchmark action parser.

Index 0 is a valid, non-progressing action in every environment, so a parser
that falls back to 0 turns a formatting failure into an apparently deliberate
choice. These tests pin the opposite behaviour: an unparseable reply is reported
as ``None`` and recorded as a parse failure by the caller.
"""

from __future__ import annotations

import pytest

from benchmark_models import _extract_action_index, extract_action_with_status

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
            "2 is not an action",
            "There are 2 degraded nodes on port 8080.",
            "I should not run patch_health_report, instead I want attempt_worker_recovery.",
            '{"action": "nonexistent_action"}',
            '{"action_index": "invalid"}',
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
        idx, status = extract_action_with_status('{"action_index": 3}', ACTION_NAMES)
        assert idx == 3
        assert status == "clean_json"

    def test_json_action_key_integer(self):
        idx, status = extract_action_with_status('{"action": 7}', ACTION_NAMES)
        assert idx == 7
        assert status == "clean_json"

    def test_json_action_name(self):
        idx, status = extract_action_with_status('{"action": "read_metrics"}', ACTION_NAMES)
        assert idx == 3
        assert status == "clean_json"

    def test_fenced_json_block(self):
        idx, status = extract_action_with_status('```json\n{"action_index": 1}\n```', ACTION_NAMES)
        assert idx == 1
        assert status == "clean_json"

    def test_regex_fallback_inside_prose(self):
        idx, status = extract_action_with_status('I choose {"action_index": 6} now', ACTION_NAMES)
        assert idx == 6
        assert status == "clean_json"

    def test_action_name_mentioned_in_prose(self):
        content = "I will run_retention_audit_diagnostic next"
        idx, status = extract_action_with_status(content, ACTION_NAMES)
        assert idx == 6
        assert status == "action_name"

    def test_leading_integer_fallback(self):
        idx, status = extract_action_with_status("2 - let's look at the logs", ACTION_NAMES)
        assert idx == 2
        assert status == "explicit_choice"

    def test_choice_prefix_fallback(self):
        idx, status = extract_action_with_status("Choice: 3", ACTION_NAMES)
        assert idx == 3
        assert status == "explicit_choice"

    def test_zero_is_still_valid_when_explicit(self):
        idx, status = extract_action_with_status('{"action_index": 0}', ACTION_NAMES)
        assert idx == 0
        assert status == "clean_json"
