import { describe, it, expect, beforeEach } from "vitest";
import crypto from "node:crypto";
import os from "node:os";
import path from "node:path";
import { promises as fs } from "node:fs";
import { verifyToken, activateLicense, loadLicense } from "./license";

// Issue a token the same way the Python vendor tool does, with a keypair we
// also install as the trusted public key — this proves the Node verifier
// accepts tokens produced by the (Python) signer.
function makeSigner() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const pubPem = publicKey.export({ type: "spki", format: "pem" }).toString();
  process.env.EXAM_STUDIO_LICENSE_PUBKEY = pubPem;
  return (opts: { sub?: string; plan?: string; iat?: number; exp?: number } = {}) => {
    const payload = {
      sub: opts.sub ?? "buyer@example.com",
      plan: opts.plan ?? "pro",
      iat: opts.iat ?? Math.floor(Date.now() / 1000),
      exp: opts.exp ?? 0,
    };
    // Must match Python: sorted keys, compact separators.
    const body = Buffer.from(
      JSON.stringify(payload, Object.keys(payload).sort() as any),
      "utf-8"
    );
    const sig = crypto.sign(null, body, privateKey);
    return `${body.toString("base64url")}.${sig.toString("base64url")}`;
  };
}

describe("verifyToken", () => {
  beforeEach(() => {
    delete process.env.EXAM_STUDIO_DEV;
  });

  it("accepts a valid perpetual token", () => {
    const issue = makeSigner();
    const info = verifyToken(issue({ exp: 0 }));
    expect(info.valid).toBe(true);
    expect(info.subject).toBe("buyer@example.com");
    expect(info.plan).toBe("pro");
  });

  it("rejects an expired token", () => {
    const issue = makeSigner();
    const info = verifyToken(issue({ exp: Math.floor(Date.now() / 1000) - 10 }));
    expect(info.valid).toBe(false);
    expect(info.reason).toContain("만료");
  });

  it("rejects a tampered payload", () => {
    const issue = makeSigner();
    const token = issue({ sub: "a@b.com" });
    const sig = token.split(".")[1];
    const forged = Buffer.from(
      JSON.stringify({ exp: 0, iat: 1, plan: "pro", sub: "hacker@evil.com" }),
      "utf-8"
    ).toString("base64url");
    expect(verifyToken(`${forged}.${sig}`).valid).toBe(false);
  });

  it("rejects garbage", () => {
    makeSigner();
    expect(verifyToken("nonsense").valid).toBe(false);
    expect(verifyToken("").valid).toBe(false);
  });
});

describe("activate / load", () => {
  beforeEach(() => {
    process.env.EXAM_STUDIO_LICENSE = path.join(
      os.tmpdir(),
      `lic-${crypto.randomUUID()}.json`
    );
    delete process.env.EXAM_STUDIO_DEV;
  });

  it("persists and reloads a valid license", async () => {
    const issue = makeSigner();
    const info = await activateLicense(issue());
    expect(info.valid).toBe(true);
    const stat = await fs.stat(process.env.EXAM_STUDIO_LICENSE!);
    expect(stat.mode & 0o777).toBe(0o600);
    expect((await loadLicense()).valid).toBe(true);
  });

  it("does not persist an invalid license", async () => {
    makeSigner();
    const info = await activateLicense("bad.token");
    expect(info.valid).toBe(false);
    await expect(fs.stat(process.env.EXAM_STUDIO_LICENSE!)).rejects.toThrow();
  });
});
