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
