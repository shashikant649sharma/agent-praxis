import pytest

from benchmark_models import (
    _effective_provider,
    _extract_action_index,
    apply_context_policy,
    is_meta_model,
)
from benchmark_models import (
    resolve_model_alias as bm_resolve_alias,
)
from eval_meta_frontier_suite import (
    resolve_model_alias as meta_resolve_alias,
)


def test_meta_alias_resolution():
    """Verify Meta shorthand aliases resolve to canonical identifiers."""
    assert bm_resolve_alias("llama-3.3-70b") == "meta-llama/Llama-3.3-70B-Instruct"
    assert bm_resolve_alias("llama-3.1-405b") == "meta-llama/Llama-3.1-405B-Instruct"
    assert bm_resolve_alias("llama-3.2-3b") == "meta-llama/Llama-3.2-3B-Instruct"
    assert meta_resolve_alias("llama-3.3-70b") == "meta-llama/Llama-3.3-70B-Instruct"


def test_is_meta_model_detection():
    """Verify is_meta_model accurately identifies Meta models."""
    assert is_meta_model("meta-llama/Llama-3.3-70B-Instruct") is True
    assert is_meta_model("llama-3.3-70b") is True
    assert is_meta_model("custom-model", provider="meta") is True
    assert is_meta_model("qwen/qwen-2.5-32b") is False
    assert is_meta_model("gemma2:9b") is False


def test_provider_routing_precedence():
    """Verify _effective_provider routes correctly among meta, groq, and ollama."""
    assert _effective_provider("llama-3.3-70b") == "meta"
    assert _effective_provider("meta-llama/Llama-3.1-405B-Instruct") == "meta"
    assert _effective_provider("qwen/qwen-2.5-32b") == "groq"
    assert _effective_provider("openai/gpt-oss-120b") == "groq"
    assert _effective_provider("llama3.2:3b") == "ollama"
    assert _effective_provider("gemma2:9b") == "ollama"


def test_action_extraction_resilience():
    """Verify action index extraction handles JSON formatting and markdown blocks."""
    action_names = ["inspect_logs", "restart_pod", "finalize"]

    # Clean JSON
    idx = _extract_action_index('{"action_index": 2}', action_names)
    assert idx == 2

    # Markdown fenced JSON
    idx = _extract_action_index('```json\n{"action_index": 1}\n```', action_names)
    assert idx == 1

    # Text referencing action name
    idx = _extract_action_index("I will choose inspect_logs to see what happened.", action_names)
    assert idx == 0

    # Unparseable response returns None (never default to zero)
    idx = _extract_action_index("I am thinking about this deeply...", action_names)
    assert idx is None


def test_apply_context_policy():
    """Verify context management policy pruning and provenance reporting."""
    msgs = [{"role": "system", "content": "system prompt"}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(10)
    ]
    # Total 11 messages (1 system + 10 turns)

    # 1. Full history keeps everything
    pruned_full, meta_full = apply_context_policy(msgs, policy="full_history")
    assert len(pruned_full) == 11
    assert meta_full["sent_messages"] == 11
    assert meta_full["omitted_messages"] == 0

    # 2. Sliding window 4 keeps message 0 + last 4 messages = 5 messages
    pruned_w4, meta_w4 = apply_context_policy(msgs, policy="sliding_window_4")
    assert len(pruned_w4) == 5
    assert pruned_w4[0] == msgs[0]
    assert pruned_w4[1:] == msgs[-4:]
    assert meta_w4["sent_messages"] == 5
    assert meta_w4["omitted_messages"] == 6

    # 3. Sliding window 8 keeps message 0 + last 8 messages = 9 messages
    pruned_w8, meta_w8 = apply_context_policy(msgs, policy="sliding_window_8")
    assert len(pruned_w8) == 9
    assert pruned_w8[0] == msgs[0]
    assert pruned_w8[1:] == msgs[-8:]
    assert meta_w8["sent_messages"] == 9
    assert meta_w8["omitted_messages"] == 2

    # 4. Short messages not pruned
    short_msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    pruned_short, meta_short = apply_context_policy(short_msgs, policy="sliding_window_4")
    assert len(pruned_short) == 2
    assert meta_short["omitted_messages"] == 0

    # 5. Invalid policy raises ValueError
    with pytest.raises(ValueError, match="Unsupported context policy"):
        apply_context_policy(msgs, policy="unknown_policy")


def test_baseten_provider_routing(monkeypatch):
    """Verify Baseten provider routing and configuration detection."""
    from agent_praxis.framework.prompt import ActionOutcomeKind, query_provider_action
    from eval_meta_frontier_suite import get_active_provider_config

    # Explicit provider routing
    assert _effective_provider("custom-model", provider="baseten") == "baseten"

    # Environment variable routing
    monkeypatch.setenv("BASETEN_API_KEY", "test-baseten-key")
    assert _effective_provider("meta/muse-spark-open") == "baseten"
    prov_name, prov_url, prov_key, headers = get_active_provider_config()
    assert prov_name == "baseten"
    assert (
        "Bearer test-baseten-key" in headers["Authorization"]
        or "Api-Key test-baseten-key" in headers["Authorization"]
    )

    # When no keys configured, frontier Muse Spark fails honestly with PROVIDER_ERROR
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("LLAMA_API_KEY", raising=False)
    resp = query_provider_action(
        "meta/muse-spark-open", [{"role": "user", "content": "hi"}], ["action1", "finalize"]
    )
    assert resp.outcome_kind == ActionOutcomeKind.PROVIDER_ERROR
    assert "requires BASETEN_API_KEY or META_API_KEY" in resp.error_message


def test_openai_provider_routing(monkeypatch):
    """Verify generic OpenAI-compatible provider routing and error handling."""
    from agent_praxis.framework.prompt import ActionOutcomeKind, query_provider_action

    assert _effective_provider("custom-model", provider="openai") == "openai"
    assert _effective_provider("custom-model", provider="openai_compatible") == "openai"

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    assert _effective_provider("deepseek/deepseek-chat") == "openai"
    assert _effective_provider("gpt-4o") == "openai"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = query_provider_action(
        "deepseek/deepseek-chat",
        [{"role": "user", "content": "hi"}],
        ["action1", "finalize"],
        provider="openai",
    )
    assert resp.outcome_kind == ActionOutcomeKind.PROVIDER_ERROR
    assert "OPENAI_API_KEY" in resp.error_message


def test_hackathon_comparison_real_inference_isolation():
    """Verify run_hackathon_model_comparison executes real inference or explicit oracle control."""
    from run_hackathon_model_comparison import evaluate_model_on_env

    # 1. Oracle policy is explicitly typed as handcrafted_oracle_control
    oracle_res = evaluate_model_on_env(
        "scripted-oracle-control", "othello", seed=20261115, is_oracle_control=True
    )
    assert oracle_res["model"] == "scripted-oracle-control"
    assert oracle_res["policy_type"] == "handcrafted_oracle_control"
    assert oracle_res["score"] > 0.0
    assert "Reference oracle control policy" in oracle_res["note"]

    # 2. Frontier model requires valid provider credentials and does NOT secretly run the oracle script
    frontier_res = evaluate_model_on_env(
        "meta/muse-spark-open", "othello", seed=20261115, is_oracle_control=False
    )
    # Without keys, it must report error truthfully, not fake a 0.995 pass
    assert frontier_res["task_success"] is False
    assert "error" in frontier_res
