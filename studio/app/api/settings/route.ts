import { NextRequest, NextResponse } from "next/server";
import { loadSettings, saveSettings, maskKey, StudioSettings } from "@/lib/settings";

export const runtime = "nodejs";

// GET: return settings WITHOUT the raw key (masked hint + boolean only).
export async function GET() {
  const s = await loadSettings();
  return NextResponse.json({
    provider: s.provider,
    models: s.models,
    dpi: s.dpi,
    useVision: s.useVision,
    columns: s.columns,
    generateSolutions: s.generateSolutions,
    examHeader: s.examHeader,
    hasKey: Boolean(s.anthropicApiKey),
    keyHint: maskKey(s.anthropicApiKey),
  });
}

// POST: persist changes. An empty/omitted key leaves the stored key untouched.
export async function POST(req: NextRequest) {
  const body = (await req.json()) as Partial<StudioSettings> & { anthropicApiKey?: string };
  const patch: Partial<StudioSettings> = {};

  if (typeof body.provider === "string") patch.provider = body.provider;
  if (body.models) patch.models = body.models;
  if (typeof body.dpi === "number") patch.dpi = body.dpi;
  if (typeof body.useVision === "boolean") patch.useVision = body.useVision;
  if (typeof body.columns === "number") patch.columns = body.columns;
  if (typeof body.generateSolutions === "boolean") patch.generateSolutions = body.generateSolutions;
  if (typeof body.examHeader === "boolean") patch.examHeader = body.examHeader;
  // Empty string with the explicit clear flag removes the stored key.
  if ((body as { clearKey?: boolean }).clearKey === true) {
    patch.anthropicApiKey = "";
  } else if (typeof body.anthropicApiKey === "string" && body.anthropicApiKey.trim() !== "") {
    patch.anthropicApiKey = body.anthropicApiKey.trim();
  }

  const saved = await saveSettings(patch);
  return NextResponse.json({
    ok: true,
    hasKey: Boolean(saved.anthropicApiKey),
    keyHint: maskKey(saved.anthropicApiKey),
  });
}
