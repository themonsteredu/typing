"use client";

import { useEffect, useRef, useState } from "react";

interface LogLine {
  text: string;
  error?: boolean;
}

const STEPS = ["추출", "풀이 생성", "도형 처리", "HWPX 조립"];

export default function HomePage() {
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const [licensed, setLicensed] = useState<boolean | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [step, setStep] = useState(-1);
  const [jobId, setJobId] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((s) => setHasKey(Boolean(s.hasKey)))
      .catch(() => setHasKey(false));
    fetch("/api/license")
      .then((r) => r.json())
      .then((l) => setLicensed(Boolean(l.valid)))
      .catch(() => setLicensed(false));
  }, []);

  useEffect(() => {
    consoleRef.current?.scrollTo(0, consoleRef.current.scrollHeight);
  }, [logs]);

  const append = (text: string, error = false) =>
    setLogs((prev) => [...prev, { text, error }]);

  const onPick = (f: File | null) => {
    if (f && !f.name.toLowerCase().endsWith(".pdf")) {
      append("PDF 파일만 업로드할 수 있습니다.", true);
      return;
    }
    setFile(f);
    setDone(false);
  };

  async function start() {
    if (!file) return;
    setRunning(true);
    setDone(false);
    setLogs([]);
    setStep(0);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await fetch("/api/upload", { method: "POST", body: fd });
      if (!up.ok) throw new Error((await up.json()).error ?? "업로드 실패");
      const { jobId: id } = await up.json();
      setJobId(id);
      append(`업로드 완료: ${file.name}`);

      await new Promise<void>((resolve) => {
        const es = new EventSource(`/api/run?job=${id}`);
        es.onmessage = (ev) => {
          const data = JSON.parse(ev.data);
          if (data.type === "log" && data.message) {
            append(data.message);
            advanceStep(data.message);
          } else if (data.type === "error") {
            append(data.message ?? "엔진 오류", true);
            es.close();
            resolve();
          } else if (data.type === "done") {
            setStep(STEPS.length);
            setDone(true);
            append("완료되었습니다. 아래에서 HWPX를 다운로드하세요.");
            es.close();
            resolve();
          }
        };
        es.onerror = () => {
          es.close();
          resolve();
        };
      });
    } catch (err) {
      append(err instanceof Error ? err.message : String(err), true);
    } finally {
      setRunning(false);
    }
  }

  function advanceStep(msg: string) {
    if (msg.includes("1/4")) setStep(0);
    else if (msg.includes("2/4")) setStep(1);
    else if (msg.includes("3/4")) setStep(2);
    else if (msg.includes("4/4")) setStep(3);
  }

  return (
    <>
      <h1>PDF → HWPX 변환</h1>
      <p className="subtitle">수학 시험지 PDF를 업로드하면 문제 추출부터 HWPX 조립까지 자동으로 처리합니다.</p>

      {licensed === false && (
        <div className="banner warn">
          이 프로그램을 사용하려면 라이선스 활성화가 필요합니다. <a href="/activate"><b>지금 활성화하기 →</b></a>
        </div>
      )}

      {hasKey === false && (
        <div className="banner warn">
          AI API 키가 설정되지 않았습니다. <a href="/settings"><b>설정</b></a>에서 키를 저장하면 AI 풀이가
          생성됩니다. (키 없이도 파이프라인은 동작하며, 풀이는 비워집니다.)
        </div>
      )}

      <div className="panel">
        <div
          className={`dropzone${drag ? " drag" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            onPick(e.dataTransfer.files?.[0] ?? null);
          }}
          onClick={() => document.getElementById("file-input")?.click()}
        >
          {file ? (
            <strong>{file.name}</strong>
          ) : (
            <>여기로 PDF를 드래그하거나 클릭해서 선택하세요</>
          )}
          <input
            id="file-input"
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={(e) => onPick(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="steps">
          {STEPS.map((label, i) => (
            <div
              key={label}
              className={`step${i === step ? " active" : ""}${i < step ? " done" : ""}`}
            >
              {i + 1}. {label}
            </div>
          ))}
        </div>

        <div className="row">
          <button className="btn" onClick={start} disabled={!file || running || licensed === false}>
            {running ? "처리 중…" : "파이프라인 실행"}
          </button>
          {done && jobId && (
            <>
              <a className="btn secondary" href={`/api/download?job=${jobId}`}>
                ⬇ HWPX 다운로드
              </a>
              <a className="btn secondary" href={`/api/download?job=${jobId}&kind=preview`} target="_blank">
                👁 미리보기
              </a>
            </>
          )}
        </div>
      </div>

      {logs.length > 0 && (
        <div className="panel">
          <div className="console" ref={consoleRef}>
            {logs.map((l, i) => (
              <div key={i} className={l.error ? "err" : ""}>
                {l.text}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
