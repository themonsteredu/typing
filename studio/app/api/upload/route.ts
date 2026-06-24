import { NextRequest, NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { workDir } from "@/lib/engine";

export const runtime = "nodejs";

// Accept a PDF upload, store it in a per-job work dir, return the job id.
export async function POST(req: NextRequest) {
  const form = await req.formData();
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "PDF 파일이 필요합니다." }, { status: 400 });
  }
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    return NextResponse.json({ error: "PDF 파일만 업로드할 수 있습니다." }, { status: 400 });
  }

  const jobId = crypto.randomUUID();
  const dir = workDir(jobId);
  await fs.mkdir(dir, { recursive: true });
  const bytes = Buffer.from(await file.arrayBuffer());
  await fs.writeFile(path.join(dir, "input.pdf"), bytes);

  return NextResponse.json({ jobId, name: file.name, size: bytes.length });
}
