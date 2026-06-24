"use client";

import { useEffect, useState } from "react";

const MODELS = [
  "claude-opus-4-8",
  "claude-sonnet-4-6",
  "claude-haiku-4-5-20251001",
];

export default function SettingsPage() {
  const [loaded, setLoaded] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [keyHint, setKeyHint] = useState("");
  const [models, setModels] = useState({
    extract: "claude-opus-4-8",
    generate: "claude-opus-4-8",
    figures: "claude-opus-4-8",
  });
  const [dpi, setDpi] = useState(200);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((s) => {
        setProvider(s.provider ?? "anthropic");
        setModels({ ...models, ...(s.models ?? {}) });
        setDpi(s.dpi ?? 200);
        setHasKey(Boolean(s.hasKey));
        setKeyHint(s.keyHint ?? "");
        setLoaded(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save() {
    const body: Record<string, unknown> = { provider, models, dpi };
    if (apiKey.trim()) body.anthropicApiKey = apiKey.trim();
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    setHasKey(Boolean(data.hasKey));
    setKeyHint(data.keyHint ?? "");
    setApiKey("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  if (!loaded) return <p>불러오는 중…</p>;

  return (
    <>
      <h1>설정</h1>
      <p className="subtitle">
        API 키는 이 컴퓨터의 <code>~/.exam-studio/settings.json</code> (권한 0600)에만 저장되며 외부로
        전송되지 않습니다.
      </p>

      {saved && <div className="banner ok">저장되었습니다.</div>}

      <div className="panel">
        <div className="field">
          <label>AI 제공자</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="anthropic">Anthropic (Claude)</option>
          </select>
        </div>

        <div className="field">
          <label>Anthropic API 키</label>
          <input
            type="password"
            placeholder={hasKey ? `저장됨: ${keyHint} (변경하려면 새 키 입력)` : "sk-ant-..."}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <div className="hint">
            {hasKey
              ? "키가 저장되어 있습니다. 비워두면 기존 키가 유지됩니다."
              : "키가 없으면 풀이 생성 단계는 폴백(빈 풀이)으로 동작합니다."}
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>단계별 모델</h3>
        {(["extract", "generate", "figures"] as const).map((stage) => (
          <div className="field" key={stage}>
            <label>
              {stage === "extract" ? "추출" : stage === "generate" ? "풀이 생성" : "도형 처리"}
            </label>
            <select
              value={models[stage]}
              onChange={(e) => setModels({ ...models, [stage]: e.target.value })}
            >
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        ))}

        <div className="field">
          <label>PDF 렌더링 해상도 (DPI)</label>
          <input
            type="number"
            min={72}
            max={400}
            value={dpi}
            onChange={(e) => setDpi(Number(e.target.value))}
          />
        </div>
      </div>

      <button className="btn" onClick={save}>
        저장
      </button>
    </>
  );
}
