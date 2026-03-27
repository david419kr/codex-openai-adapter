from codex_openai_adapter.services.model_resolution import (
    MODEL_CODEX,
    MODEL_GENERAL,
    exposed_model_list,
    normalize_ollama_think,
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
    models = exposed_model_list()

    assert MODEL_GENERAL in models
    assert "gpt-5.4-high" in models
    assert "gpt-5.3-codex-xhigh" in models


def test_normalize_ollama_think_false_and_none() -> None:
    assert normalize_ollama_think(False) == "none"
    assert normalize_ollama_think(True) == "medium"
    assert normalize_ollama_think("none") == "none"
    assert normalize_ollama_think("true") == "medium"
    assert normalize_ollama_think("xhigh") == "xhigh"
    assert normalize_ollama_think(None) is None
