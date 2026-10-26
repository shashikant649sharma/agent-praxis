"""Unit tests for model connectors, aliases, and provider routing."""

from benchmark_models import (
    _effective_provider,
    _extract_action_index,
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
