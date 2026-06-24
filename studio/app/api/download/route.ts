import { NextRequest } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import { workDir } from "@/lib/engine";

export const runtime = "nodejs";

// Serve the assembled HWPX (or its HTML preview) for a finished job.
export async function GET(req: NextRequest) {
  const jobId = req.nextUrl.searchParams.get("job");
  const kind = req.nextUrl.searchParams.get("kind") ?? "hwpx";
  if (!jobId || !/^[a-f0-9-]{36}$/.test(jobId)) {
    return new Response("invalid job id", { status: 400 });
  }

  const dir = workDir(jobId);
  const file = kind === "preview" ? path.join(dir, "output.html") : path.join(dir, "output.hwpx");

  try {
    const data = await fs.readFile(file);
    const isPreview = kind === "preview";
    return new Response(data, {
      headers: {
        "Content-Type": isPreview ? "text/html; charset=utf-8" : "application/hwp+zip",
        ...(isPreview
          ? {}
          : { "Content-Disposition": 'attachment; filename="exam.hwpx"' }),
      },
    });
  } catch {
    return new Response("not found", { status: 404 });
  }
}
