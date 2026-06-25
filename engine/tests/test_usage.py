from exam_engine import usage


def test_cost_for_opus():
    # 1M input @ $5, 1M output @ $25
    assert usage.cost_for("claude-opus-4-8", 1_000_000, 0) == 5.0
    assert usage.cost_for("claude-opus-4-8", 0, 1_000_000) == 25.0


def test_cost_for_haiku_cheaper():
    opus = usage.cost_for("claude-opus-4-8", 1000, 1000)
    haiku = usage.cost_for("claude-haiku-4-5", 1000, 1000)
    assert haiku < opus


def test_unknown_model_falls_back():
    assert usage.cost_for("mystery", 1_000_000, 0) == 5.0  # opus default


def test_record_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("EXAM_STUDIO_USAGE", str(tmp_path / "usage.json"))
    usage.reset()
    usage.record("claude-opus-4-8", 1000, 500, stage="extract")
    usage.record("claude-haiku-4-5", 2000, 100, stage="generate")
    s = usage.summary()
    assert s["callCount"] == 2
    assert s["totalInputTokens"] == 3000
    assert s["totalOutputTokens"] == 600
    assert s["totalCostUsd"] > 0
    assert len(s["events"]) == 2


def test_reset_clears(tmp_path, monkeypatch):
    monkeypatch.setenv("EXAM_STUDIO_USAGE", str(tmp_path / "usage.json"))
    usage.record("claude-opus-4-8", 10, 10)
    usage.reset()
    assert usage.summary()["callCount"] == 0
