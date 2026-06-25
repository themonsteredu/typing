import { spawn } from "node:child_process";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

// Locate the engine dir and a usable Python interpreter (prefer the project venv).
export function engineDir(): string {
  // Configurable so the Docker / standalone layout can point at /app/engine.
  if (process.env.EXAM_STUDIO_ENGINE_DIR) return process.env.EXAM_STUDIO_ENGINE_DIR;
  return path.join(process.cwd(), "..", "engine");
}

export function pythonBin(): string {
  const venv =
    process.platform === "win32"
      ? path.join(engineDir(), ".venv", "Scripts", "python.exe")
      : path.join(engineDir(), ".venv", "bin", "python");
  if (fs.existsSync(venv)) return venv;
  return process.env.PYTHON_BIN || "python3";
}

export interface EngineEvent {
  type: "log" | "result" | "error" | "done";
  message?: string;
  [k: string]: unknown;
}

/**
 * Run the engine CLI in `--json` mode and invoke `onEvent` for each NDJSON line.
 * Resolves with the final `result` event (or rejects on `error`).
 */
export function runEngine(
  args: string[],
  onEvent: (e: EngineEvent) => void
): Promise<EngineEvent> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin(), ["-m", "exam_engine.cli", "--json", ...args], {
      cwd: engineDir(),
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    let buffer = "";
    let result: EngineEvent | null = null;
    let errored: EngineEvent | null = null;

    const handleLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      let event: EngineEvent;
      try {
        event = JSON.parse(trimmed) as EngineEvent;
      } catch {
        event = { type: "log", message: trimmed };
      }
      if (event.type === "result") result = event;
      if (event.type === "error") errored = event;
      onEvent(event);
    };

    child.stdout.on("data", (chunk: Buffer) => {
      buffer += chunk.toString("utf-8");
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) handleLine(line);
    });

    child.stderr.on("data", (chunk: Buffer) => {
      onEvent({ type: "log", message: chunk.toString("utf-8").trimEnd() });
    });

    child.on("error", (err) => reject(err));
    child.on("close", (code) => {
      if (buffer) handleLine(buffer);
      if (errored) return reject(new Error(String(errored.message ?? "engine error")));
      if (code !== 0 && !result) return reject(new Error(`engine exited with code ${code}`));
      resolve(result ?? { type: "result" });
    });
  });
}

export function workDir(jobId: string): string {
  return path.join(os.tmpdir(), "exam-studio", jobId);
}
