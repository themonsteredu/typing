import crypto from "node:crypto";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";

// Vendor public key — MUST match engine/exam_engine/license.py.
// Override with EXAM_STUDIO_LICENSE_PUBKEY (PEM) to use your own signing key.
const DEFAULT_PUBLIC_KEY_PEM = `-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAxlMS4QobYlKgonzF55hHhbxWzwOtyOZKJGaXHTKXqI8=
-----END PUBLIC KEY-----`;

export interface LicenseInfo {
  valid: boolean;
  reason?: string;
  subject?: string;
  plan?: string;
  issuedAt?: number;
  expiresAt?: number; // 0 = perpetual
}

export function licensePath(): string {
  if (process.env.EXAM_STUDIO_LICENSE) return process.env.EXAM_STUDIO_LICENSE;
  return path.join(os.homedir(), ".exam-studio", "license.json");
}

function publicKeyPem(): string {
  return process.env.EXAM_STUDIO_LICENSE_PUBKEY || DEFAULT_PUBLIC_KEY_PEM;
}

function b64urlDecode(s: string): Buffer {
  return Buffer.from(s, "base64url");
}

export function verifyToken(token: string, now = Math.floor(Date.now() / 1000)): LicenseInfo {
  const t = (token || "").trim();
  if (!t || !t.includes(".")) {
    return { valid: false, reason: "라이선스 키 형식이 올바르지 않습니다." };
  }
  const idx = t.lastIndexOf(".");
  const payloadB64 = t.slice(0, idx);
  const sigB64 = t.slice(idx + 1);

  let payloadBytes: Buffer;
  let signature: Buffer;
  try {
    payloadBytes = b64urlDecode(payloadB64);
    signature = b64urlDecode(sigB64);
  } catch {
    return { valid: false, reason: "라이선스 키를 디코딩할 수 없습니다." };
  }

  let ok = false;
  try {
    const key = crypto.createPublicKey(publicKeyPem());
    ok = crypto.verify(null, payloadBytes, key, signature);
  } catch (err) {
    return { valid: false, reason: `검증 오류: ${err instanceof Error ? err.message : err}` };
  }
  if (!ok) {
    return { valid: false, reason: "서명이 유효하지 않습니다(위조되었거나 다른 키로 발급됨)." };
  }

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(payloadBytes.toString("utf-8"));
  } catch {
    return { valid: false, reason: "라이선스 내용을 읽을 수 없습니다." };
  }

  const exp = Number(payload.exp ?? 0) || 0;
  const base = {
    subject: String(payload.sub ?? ""),
    plan: String(payload.plan ?? ""),
    issuedAt: Number(payload.iat ?? 0) || 0,
    expiresAt: exp,
  };
  if (exp && now > exp) {
    return { valid: false, reason: "라이선스가 만료되었습니다.", ...base };
  }
  return { valid: true, ...base };
}

export async function loadLicense(): Promise<LicenseInfo> {
  if (process.env.EXAM_STUDIO_DEV === "1") {
    return { valid: true, subject: "dev", plan: "dev", expiresAt: 0 };
  }
  try {
    const raw = await fs.readFile(licensePath(), "utf-8");
    const token = JSON.parse(raw).token ?? "";
    return verifyToken(token);
  } catch {
    return { valid: false, reason: "라이선스가 등록되지 않았습니다." };
  }
}

export async function activateLicense(token: string): Promise<LicenseInfo> {
  const info = verifyToken(token);
  if (!info.valid) return info;
  const file = licensePath();
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify({ token: token.trim() }, null, 2), {
    encoding: "utf-8",
    mode: 0o600,
  });
  try {
    await fs.chmod(file, 0o600);
  } catch {
    /* best effort */
  }
  return info;
}

export async function isLicensed(): Promise<boolean> {
  return (await loadLicense()).valid;
}
