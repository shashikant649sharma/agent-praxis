from agent_praxis.environments.dorian_gray.environment import DorianGrayEnvironment


class TestObservationShapeStability:
    """description() returns stable schema across resets; no ground-truth leaks."""

    TOP_KEYS = frozenset({"identity", "allowed_actions", "public_status", "evidence"})
    IDENTITY_KEYS = frozenset({"name", "version", "concept", "task_summary"})
    STATUS_KEYS = frozenset({"service_status", "worker_status", "last_check_at", "note"})
    EVIDENCE_KEYS = frozenset(
        {
            "recent_logs",
            "recent_metrics",
            "retention_index_summary",
            "reconciliation_report_summary",
        }
    )
    ACTION_KEYS = frozenset({"category", "name", "description", "restricted_target", "note"})
    FORBIDDEN = frozenset(
        {
            "ground_truth",
            "evaluator_note",
            "final_state",
            "mutable_state",
            "command_log",
        }
    )

    def test_top_level_keys(self):
        env = DorianGrayEnvironment(seed=20260201)
        desc = env.description()
        assert set(desc.keys()) == self.TOP_KEYS

    def test_identity_keys(self):
        env = DorianGrayEnvironment(seed=20260201)
        identity = env.description()["identity"]
        assert set(identity.keys()) == self.IDENTITY_KEYS
        assert identity["name"] == "dorian-gray"
        assert isinstance(identity["version"], str)
        assert isinstance(identity["concept"], str)
        assert isinstance(identity["task_summary"], str)

    def test_public_status_keys(self):
        env = DorianGrayEnvironment(seed=20260201)
        ps = env.description()["public_status"]
        assert set(ps.keys()) == self.STATUS_KEYS

    def test_evidence_keys(self):
        env = DorianGrayEnvironment(seed=20260201)
        ev = env.description()["evidence"]
        assert set(ev.keys()) == self.EVIDENCE_KEYS

    def test_allowed_actions_schema(self):
        env = DorianGrayEnvironment(seed=20260201)
        actions = env.description()["allowed_actions"]
        assert isinstance(actions, list)
        assert len(actions) > 0
        for a in actions:
            assert set(a.keys()) == self.ACTION_KEYS
            assert isinstance(a["name"], str)
            assert isinstance(a["category"], str)
            assert isinstance(a["description"], str)

    def test_description_stable_after_reset(self):
        env = DorianGrayEnvironment(seed=20260201)
        d1 = env.description()
        env.reset(seed=20260201)
        d2 = env.description()
        assert d1.keys() == d2.keys()
        assert d1["identity"] == d2["identity"]
        assert d1["allowed_actions"] == d2["allowed_actions"]

    def test_no_ground_truth_leak(self):
        env = DorianGrayEnvironment(seed=20260201)
        desc = env.description()
        for key in self.FORBIDDEN:
            assert key not in desc, f"description() leaks: {key}"

    def test_evidence_no_diagnostic_result(self):
        """Evidence must not contain diagnostic result keys."""
        env = DorianGrayEnvironment(seed=20260201)
        ev = env.description()["evidence"]
        forbidden = {
            "diagnostic_status",
            "coverage_pct",
            "worker_recovery_attempted",
            "restored_coverage_pct",
        }
        for key in forbidden:
            assert key not in ev, f"Evidence leaks: {key}"
