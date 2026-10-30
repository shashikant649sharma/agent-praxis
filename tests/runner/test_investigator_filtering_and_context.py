"""Tests for mock investigator action filtering and strict full_history context overflow.

Verifies:
1. Investigator never executes mutating actions across all 10 environments.
2. Token boundary matching excludes substring traps like 'log_triage_declaration' and 'lock_volume_readonly'.
3. Strict full_history policy never silently removes history.
4. Input budget standardization to 7,040 tokens across all providers.
"""

from agent_praxis.actions import CANONICAL_ACTION_ORDER
from agent_praxis.framework.prompt import (
    MUTATING_ACTION_DENYLIST,
    PROVIDER_DEFAULT_CONTEXT_LIMITS,
    ContextLimits,
    get_action_from_mock,
    is_observational_action,
    render_turn_prompt,
)


class TestInvestigatorActionFiltering:
    def test_all_mutating_actions_denied(self):
        for act in MUTATING_ACTION_DENYLIST:
            assert not is_observational_action(act), f"Mutating action {act!r} was not denied!"

    def test_substring_traps_not_classified_as_observational(self):
        # Specific regression cases:
        # 'log_triage_declaration' contains 'log'
        # 'lock_volume_readonly' contains 'read'
        assert not is_observational_action("log_triage_declaration")
        assert not is_observational_action("lock_volume_readonly")
        assert not is_observational_action("patch_health_report")
        assert not is_observational_action("apply_policy_exception")
        assert not is_observational_action("relax_isolation_guards")

    def test_legitimate_observational_actions_allowed(self):
        assert is_observational_action("read_status")
        assert is_observational_action("read_logs")
        assert is_observational_action("inspect_upstream_schema")
        assert is_observational_action("query_court_records")
        assert is_observational_action("examine_precedent_archive")
        assert is_observational_action("audit_sink_idempotency")
        assert is_observational_action("disk_usage_breakdown")
        assert is_observational_action("verify_volume_integrity")

    def test_investigator_never_dispatches_mutating_action_in_any_environment(self):
        for env_id, actions in CANONICAL_ACTION_ORDER.items():
            for turn in range(30):
                # Simulate messages with action history
                history_text = " -> ".join(
                    [f"[{i}] {actions[i % len(actions)]}" for i in range(turn)]
                )
                messages = [
                    {"role": "system", "content": "system prompt"},
                    {
                        "role": "user",
                        "content": f"RECENT ACTION HISTORY:\n{history_text}\nDECISION REQUEST:\nchoose action",
                    },
                ]
                resp = get_action_from_mock("mock-investigator", messages, actions)
                chosen_act = resp.action_name
                assert chosen_act not in MUTATING_ACTION_DENYLIST, (
                    f"Mock investigator chose mutating action {chosen_act!r} in {env_id} at turn {turn}!"
                )
                assert is_observational_action(chosen_act), (
                    f"Mock investigator chose non-observational action {chosen_act!r} in {env_id}!"
                )


class TestContextBudgetAndFullHistoryIntegrity:
    def test_provider_context_limits_standardized_to_7040(self):
        for provider, limits in PROVIDER_DEFAULT_CONTEXT_LIMITS.items():
            assert limits.context_window == 8192, f"Provider {provider} context_window != 8192"
            assert limits.output_reserve == 1024, f"Provider {provider} output_reserve != 1024"
            assert limits.safety_margin == 128, f"Provider {provider} safety_margin != 128"
            assert limits.input_budget == 7040, f"Provider {provider} input_budget != 7040"

    def test_full_history_never_silently_drops_history(self):
        actions = CANONICAL_ACTION_ORDER["dorian-gray"]
        system_prompt = "You are an SRE on call."
        # Create a 16-turn history
        history = [(i, actions[i % len(actions)]) for i in range(16)]
        # A massive observation that would exceed a small variable budget
        massive_obs = "OBSERVATION ERROR:\n" + ("trace dump line\n" * 400)

        # Normal 7040 budget: history must be 100% intact, zero dropped messages
        res = render_turn_prompt(
            system_prompt=system_prompt,
            action_names=actions,
            obs=massive_obs,
            action_history=history,
            context_policy="full_history",
        )
        assert res.dropped_messages_count == 0
        assert not res.context_overflow
        # History section must contain all 16 turns
        for idx, act in history:
            assert f"[{idx}] {act}" in res.user_prompt

    def test_full_history_produces_explicit_overflow_when_mandatory_and_history_exceed_budget(self):
        actions = CANONICAL_ACTION_ORDER["catch-22"]
        huge_history = [(i, f"very_long_action_step_name_{i}") for i in range(100)]
        # Tiny budget where mandatory + history cannot fit
        tiny_limits = ContextLimits(context_window=512, output_reserve=256, safety_margin=128)
        # B_input = 128

        res = render_turn_prompt(
            system_prompt="Short prompt",
            action_names=actions,
            obs="Short obs",
            action_history=huge_history,
            context_policy="full_history",
            limits=tiny_limits,
        )
        assert res.context_overflow is True
        assert res.truncation_method == "context_overflow"
        # Crucial invariant: full_history must NEVER silently remove history
        assert res.dropped_messages_count == 0
