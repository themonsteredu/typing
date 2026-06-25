"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface LicenseInfo {
  valid: boolean;
  reason?: string;
  subject?: string;
  plan?: string;
  expiresAt?: number;
}

function fmtExpiry(exp?: number): string {
  if (!exp) return "무기한";
  return new Date(exp * 1000).toLocaleDateString("ko-KR");
}

export default function ActivatePage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [info, setInfo] = useState<LicenseInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/license")
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => setInfo({ valid: false }));
  }, []);

  async function activate() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/license", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim() }),
      });
      const data: LicenseInfo = await res.json();
      setInfo(data);
      if (data.valid) {
        setTimeout(() => router.push("/"), 800);
      } else {
        setError(data.reason ?? "활성화에 실패했습니다.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>라이선스 활성화</h1>
      <p className="subtitle">
        구매 시 발급받은 라이선스 키를 입력하세요. 키는 이 컴퓨터에만 저장되며 외부로 전송되지 않습니다.
      </p>

      {info?.valid && (
        <div className="banner ok">
          활성화됨 — {info.subject} · 플랜 {info.plan} · 만료 {fmtExpiry(info.expiresAt)}
        </div>
      )}
      {error && <div className="banner warn">{error}</div>}

      <div className="panel">
        <div className="field">
          <label>라이선스 키</label>
          <input
            type="text"
            placeholder="예) eyJ...payload....서명"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <div className="hint">키 형식: 서명된 토큰(payload.signature)</div>
        </div>
        <button className="btn" onClick={activate} disabled={busy || !token.trim()}>
          {busy ? "확인 중…" : "활성화"}
        </button>
      </div>
    </>
  );
}
