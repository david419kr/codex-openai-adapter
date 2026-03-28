from codex_openai_ollama_proxy.services.model_resolution import (
    FALLBACK_BASE_MODELS,
    MODEL_CODEX,
    MODEL_GENERAL,
    exposed_model_list,
    is_known_model,
    normalize_ollama_think,
    resolve_model_alias,
    resolve_model_and_reasoning,
    resolve_temperature,
)


def test_explicit_reasoning_effort_overrides_suffix() -> None:
    model, reasoning = resolve_model_and_reasoning(
        "gpt-5.4-low",
        {"effort": "medium", "summary": "auto"},
        "high",
    )

    assert model == MODEL_GENERAL
    assert reasoning == {"effort": "high", "summary": "auto"}


def test_gpt54_allows_none_reasoning() -> None:
    model, reasoning = resolve_model_and_reasoning(MODEL_GENERAL, None, "none")

    assert model == MODEL_GENERAL
    assert reasoning == {"effort": "none"}


def test_gpt53_codex_rejects_none_reasoning() -> None:
    model, reasoning = resolve_model_and_reasoning(MODEL_CODEX, {"effort": "none"}, None)

    assert model == MODEL_CODEX
    assert reasoning is None


def test_temperature_only_passes_for_gpt54_none() -> None:
    assert resolve_temperature(MODEL_GENERAL, MODEL_GENERAL, None, 0.2) == 0.2
    assert resolve_temperature("gpt-5.4-high", MODEL_GENERAL, {"effort": "high"}, 0.2) is None
    assert resolve_temperature(MODEL_CODEX, MODEL_CODEX, None, 0.2) is None


def test_exposed_models_include_suffix_variants() -> None:
    models = exposed_model_list(FALLBACK_BASE_MODELS)

    assert MODEL_GENERAL in models
    assert "gpt-5.4-high" in models
    assert "gpt-5.3-codex-xhigh" in models


def test_dynamic_model_alias_resolution_prefers_longest_base_model() -> None:
    base_models = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]

    backend_model, effort = resolve_model_alias("gpt-5.4-mini-high", base_models)

    assert backend_model == "gpt-5.4-mini"
    assert effort == "high"


def test_dynamic_model_behaves_like_gpt54_for_none_and_temperature() -> None:
    base_models = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]

    backend_model, reasoning = resolve_model_and_reasoning(
        "gpt-5.4-mini",
        None,
        "none",
        base_models,
    )

    assert backend_model == "gpt-5.4-mini"
    assert reasoning == {"effort": "none"}
    assert resolve_temperature("gpt-5.4-mini", backend_model, reasoning, 0.2) == 0.2


def test_is_known_model_recognizes_dynamic_suffix_aliases() -> None:
    base_models = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]

    assert is_known_model("gpt-5.4-mini", base_models) is True
    assert is_known_model("gpt-5.4-mini-xhigh", base_models) is True
    assert is_known_model("gpt-9.9", base_models) is False


def test_normalize_ollama_think_false_and_none() -> None:
    assert normalize_ollama_think(False) == "none"
    assert normalize_ollama_think(True) == "medium"
    assert normalize_ollama_think("none") == "none"
    assert normalize_ollama_think("true") == "medium"
    assert normalize_ollama_think("xhigh") == "xhigh"
    assert normalize_ollama_think(None) is None
