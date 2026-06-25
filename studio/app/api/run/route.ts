import { NextRequest } from "next/server";
import path from "node:path";
import { runEngine, workDir, EngineEvent } from "@/lib/engine";
import { isLicensed } from "@/lib/license";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// SSE endpoint: runs the full pipeline for a job and streams log events.
export async function GET(req: NextRequest) {
  if (!(await isLicensed())) {
    return new Response("license required", { status: 403 });
  }
  const jobId = req.nextUrl.searchParams.get("job");
  if (!jobId || !/^[a-f0-9-]{36}$/.test(jobId)) {
    return new Response("invalid job id", { status: 400 });
  }

  const dir = workDir(jobId);
  const input = path.join(dir, "input.pdf");
  const output = path.join(dir, "output.hwpx");
  // Per-run override: ?solutions=0 skips 풀이 generation for this document.
  const noSolutions = req.nextUrl.searchParams.get("solutions") === "0";
  const runArgs = ["run", input, "--out", output, "--work", path.join(dir, "work")];
  if (noSolutions) runArgs.push("--no-solutions");

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: EngineEvent) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      };
      try {
        const result = await runEngine(runArgs, send);
        send({ ...result, type: "done" });
      } catch (err) {
        send({ type: "error", message: err instanceof Error ? err.message : String(err) });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
