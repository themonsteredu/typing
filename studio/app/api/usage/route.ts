import { NextResponse } from "next/server";
import { loadUsage, resetUsage } from "@/lib/usage";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json(await loadUsage());
}

export async function DELETE() {
  await resetUsage();
  return NextResponse.json({ ok: true });
}
