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
  const [useVision, setUseVision] = useState(true);
  const [columns, setColumns] = useState(1);
  const [generateSolutions, setGenerateSolutions] = useState(true);
  const [examHeader, setExamHeader] = useState(true);
  const [useEquations, setUseEquations] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((s) => {
        setProvider(s.provider ?? "anthropic");
        setModels({ ...models, ...(s.models ?? {}) });
        setDpi(s.dpi ?? 200);
        setUseVision(s.useVision !== false);
        setColumns(s.columns ?? 1);
        setGenerateSolutions(s.generateSolutions !== false);
        setExamHeader(s.examHeader !== false);
        setUseEquations(s.useEquations !== false);
        setHasKey(Boolean(s.hasKey));
        setKeyHint(s.keyHint ?? "");
        setLoaded(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save(extra: Record<string, unknown> = {}) {
    const body: Record<string, unknown> = {
      provider, models, dpi, useVision, columns, generateSolutions, examHeader, useEquations,
      ...extra,
    };
    if (!extra.clearKey && apiKey.trim()) body.anthropicApiKey = apiKey.trim();
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

  async function clearKey() {
    if (!confirm("저장된 API 키를 삭제할까요?")) return;
    await save({ clearKey: true });
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
              : "키가 없으면 비전/풀이 단계가 동작하지 않습니다(일반 텍스트 추출로 폴백)."}
          </div>
          {hasKey && (
            <button className="btn secondary" style={{ marginTop: "0.6rem" }} onClick={clearKey}>
              저장된 키 삭제
            </button>
          )}
        </div>

        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={useVision}
              onChange={(e) => setUseVision(e.target.checked)}
              style={{ width: "auto", marginRight: "0.5rem" }}
            />
            AI 비전으로 문제 읽기 (수식 깨짐 방지, 권장)
          </label>
          <div className="hint">
            페이지를 이미지로 만들어 Claude가 수식까지 읽습니다. 끄면 빠르지만 수식이 깨질 수 있어요.
            (페이지당 약 수십~수백원의 토큰 비용 발생 — <a href="/usage">지출</a>에서 확인)
          </div>
        </div>

        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={useEquations}
              onChange={(e) => setUseEquations(e.target.checked)}
              style={{ width: "auto", marginRight: "0.5rem" }}
            />
            수식을 한글 수식 개체로 (분수·지수·루트 깔끔하게)
          </label>
          <div className="hint">
            켜면 AI가 한글 수식 스크립트로 작성해 제대로 된 수식으로 들어갑니다. 끄면 평문(x^2, a/b).
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

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>문서 레이아웃</h3>
        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={examHeader}
              onChange={(e) => setExamHeader(e.target.checked)}
              style={{ width: "auto", marginRight: "0.5rem" }}
            />
            시험지 머리말 (제목 + 이름·학년·날짜 기입란)
          </label>
        </div>
        <div className="field">
          <label>단 나누기</label>
          <select value={columns} onChange={(e) => setColumns(Number(e.target.value))}>
            <option value={1}>1단 (기본)</option>
            <option value={2}>2단 (시험지 형식)</option>
          </select>
          <div className="hint">
            2단은 신문식 좌→우 배치입니다. (실제 한글에서 열어 확인을 권장 — 문제 있으면 1단으로 되돌리세요)
          </div>
        </div>
        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={generateSolutions}
              onChange={(e) => setGenerateSolutions(e.target.checked)}
              style={{ width: "auto", marginRight: "0.5rem" }}
            />
            기본으로 풀이(해설) 생성
          </label>
          <div className="hint">
            여기는 기본값이고, 메인 화면에서 변환할 때마다 끄고 켤 수 있어요.
          </div>
        </div>
      </div>

      <button className="btn" onClick={() => save()}>
        저장
      </button>
    </>
  );
}
