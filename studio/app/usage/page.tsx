"use client";

import { useEffect, useState } from "react";

interface UsageEvent {
  ts: number;
  stage: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}
interface UsageSummary {
  totalCostUsd: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  callCount: number;
  events: UsageEvent[];
}

const STAGE_KO: Record<string, string> = {
  extract: "추출(비전)",
  generate: "풀이 생성",
  figures: "도형",
};

export default function UsagePage() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    fetch("/api/usage")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));

  useEffect(() => {
    load();
  }, []);

  async function reset() {
    if (!confirm("사용량 기록을 모두 지울까요? (실제 청구와는 별개의 자체 집계입니다)")) return;
    setBusy(true);
    await fetch("/api/usage", { method: "DELETE" });
    await load();
    setBusy(false);
  }

  if (!data) return <p>불러오는 중…</p>;

  const usd = (n: number) => `$${n.toFixed(4)}`;
  const krwApprox = (n: number) => `≈ ${Math.round(n * 1400).toLocaleString()}원`;

  return (
    <>
      <h1>지출 / 사용량</h1>
      <p className="subtitle">
        AI 토큰 사용량과 예상 비용을 자체 집계합니다. (Anthropic 공식 청구가 아닌 참고용 추정치)
      </p>

      <div className="panel">
        <div className="row" style={{ gap: "2rem" }}>
          <div>
            <div className="hint">누적 예상 비용</div>
            <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--accent-hover)" }}>
              {usd(data.totalCostUsd)}
            </div>
            <div className="hint">{krwApprox(data.totalCostUsd)} (환율 1400원 가정)</div>
          </div>
          <div>
            <div className="hint">호출 횟수</div>
            <div style={{ fontSize: "1.8rem", fontWeight: 700 }}>{data.callCount}</div>
          </div>
          <div>
            <div className="hint">토큰 (입력 / 출력)</div>
            <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>
              {data.totalInputTokens.toLocaleString()} / {data.totalOutputTokens.toLocaleString()}
            </div>
          </div>
        </div>
        <div className="row" style={{ marginTop: "1rem" }}>
          <button className="btn secondary" onClick={reset} disabled={busy}>
            기록 초기화
          </button>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>최근 호출</h3>
        {data.events.length === 0 ? (
          <p className="hint">아직 AI 호출 기록이 없습니다. 설정에서 키를 넣고 파이프라인을 실행해 보세요.</p>
        ) : (
          <div className="console" style={{ maxHeight: 360 }}>
            {data.events.map((e, i) => (
              <div key={i}>
                {STAGE_KO[e.stage] ?? e.stage} · {e.model} · in {e.inputTokens} / out{" "}
                {e.outputTokens} · {usd(e.costUsd)}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
