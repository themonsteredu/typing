import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";

// Same file the Python engine reads (engine/exam_engine/settings.py).
export function settingsPath(): string {
  if (process.env.EXAM_STUDIO_SETTINGS) {
    return process.env.EXAM_STUDIO_SETTINGS;
  }
  return path.join(os.homedir(), ".exam-studio", "settings.json");
}

export interface StudioSettings {
  provider: string;
  anthropicApiKey: string;
  models: { extract: string; generate: string; figures: string };
  dpi: number;
  useVision: boolean;
  columns: number;
  generateSolutions: boolean;
  examHeader: boolean;
  useEquations: boolean;
  cropMode: boolean;
}

export const DEFAULT_SETTINGS: StudioSettings = {
  provider: "anthropic",
  anthropicApiKey: "",
  models: {
    extract: "claude-opus-4-8",
    generate: "claude-opus-4-8",
    figures: "claude-opus-4-8",
  },
  dpi: 200,
  useVision: true,
  columns: 1,
  generateSolutions: true,
  examHeader: true,
  useEquations: true,
  cropMode: false,
};

export async function loadSettings(): Promise<StudioSettings> {
  try {
    const raw = await fs.readFile(settingsPath(), "utf-8");
    const data = JSON.parse(raw);
    return {
      ...DEFAULT_SETTINGS,
      ...data,
      models: { ...DEFAULT_SETTINGS.models, ...(data.models ?? {}) },
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function saveSettings(patch: Partial<StudioSettings>): Promise<StudioSettings> {
  const current = await loadSettings();
  const next: StudioSettings = {
    ...current,
    ...patch,
    models: { ...current.models, ...(patch.models ?? {}) },
  };
  const file = settingsPath();
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(next, null, 2), { encoding: "utf-8", mode: 0o600 });
  try {
    await fs.chmod(file, 0o600);
  } catch {
    /* best effort on non-POSIX */
  }
  return next;
}

// Never ship the raw key to the browser — show a masked hint instead.
export function maskKey(key: string): string {
  if (!key) return "";
  if (key.length <= 10) return "•".repeat(key.length);
  return `${key.slice(0, 7)}…${key.slice(-4)}`;
}
