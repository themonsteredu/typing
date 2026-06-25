import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";

// Same file the Python engine writes (engine/exam_engine/usage.py).
export function usagePath(): string {
  if (process.env.EXAM_STUDIO_USAGE) return process.env.EXAM_STUDIO_USAGE;
  return path.join(os.homedir(), ".exam-studio", "usage.json");
}

export interface UsageEvent {
  ts: number;
  stage: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheRead: number;
  cacheCreation: number;
  costUsd: number;
}

export interface UsageSummary {
  totalCostUsd: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  callCount: number;
  events: UsageEvent[];
}

export async function loadUsage(): Promise<UsageSummary> {
  let events: UsageEvent[] = [];
  try {
    const raw = await fs.readFile(usagePath(), "utf-8");
    events = (JSON.parse(raw).events ?? []) as UsageEvent[];
  } catch {
    events = [];
  }
  const totalCostUsd = Number(
    events.reduce((s, e) => s + (e.costUsd ?? 0), 0).toFixed(4)
  );
  return {
    totalCostUsd,
    totalInputTokens: events.reduce((s, e) => s + (e.inputTokens ?? 0), 0),
    totalOutputTokens: events.reduce((s, e) => s + (e.outputTokens ?? 0), 0),
    callCount: events.length,
    events: events.slice(-100).reverse(),
  };
}

export async function resetUsage(): Promise<void> {
  const file = usagePath();
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify({ events: [] }, null, 2), "utf-8");
}
