import { describe, it, expect, beforeEach } from "vitest";
import os from "node:os";
import path from "node:path";
import { promises as fs } from "node:fs";
import crypto from "node:crypto";
import { loadSettings, saveSettings, maskKey, DEFAULT_SETTINGS } from "./settings";

describe("maskKey", () => {
  it("masks short keys completely", () => {
    expect(maskKey("short")).toBe("•••••");
  });
  it("shows a hint for long keys", () => {
    expect(maskKey("sk-ant-abcdefghijkl")).toBe("sk-ant-…ijkl");
  });
  it("returns empty for empty", () => {
    expect(maskKey("")).toBe("");
  });
});

describe("settings store", () => {
  beforeEach(() => {
    const tmp = path.join(os.tmpdir(), `exam-settings-${crypto.randomUUID()}.json`);
    process.env.EXAM_STUDIO_SETTINGS = tmp;
  });

  it("returns defaults when no file exists", async () => {
    const s = await loadSettings();
    expect(s.provider).toBe(DEFAULT_SETTINGS.provider);
    expect(s.anthropicApiKey).toBe("");
  });

  it("round-trips a saved key and merges model defaults", async () => {
    await saveSettings({ anthropicApiKey: "sk-ant-xyz", models: { generate: "claude-sonnet-4-6" } as any });
    const s = await loadSettings();
    expect(s.anthropicApiKey).toBe("sk-ant-xyz");
    expect(s.models.generate).toBe("claude-sonnet-4-6");
    expect(s.models.extract).toBe(DEFAULT_SETTINGS.models.extract);
  });

  it("writes the file with 0600 permissions", async () => {
    await saveSettings({ anthropicApiKey: "secret" });
    const stat = await fs.stat(process.env.EXAM_STUDIO_SETTINGS!);
    expect(stat.mode & 0o777).toBe(0o600);
  });
});
