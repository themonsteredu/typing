import json

from exam_engine import settings as settings_mod
from exam_engine.settings import Settings


def test_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    monkeypatch.setenv("EXAM_STUDIO_SETTINGS", str(target))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cfg = Settings.from_dict({})
    cfg.anthropic_api_key = "sk-ant-test"
    cfg.models["generate"] = "claude-opus-4-8"
    settings_mod.save(cfg)

    assert target.exists()
    loaded = settings_mod.load()
    assert loaded.anthropic_api_key == "sk-ant-test"
    assert loaded.model_for("generate") == "claude-opus-4-8"


def test_env_key_overrides_stored(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"anthropicApiKey": "stored"}))
    monkeypatch.setenv("EXAM_STUDIO_SETTINGS", str(target))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")

    cfg = settings_mod.load()
    assert cfg.api_key() == "from-env"


def test_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EXAM_STUDIO_SETTINGS", str(tmp_path / "nope.json"))
    cfg = settings_mod.load()
    assert cfg.provider == "anthropic"
    assert cfg.model_for("extract")
