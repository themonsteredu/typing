import { NextRequest, NextResponse } from "next/server";
import { loadLicense, activateLicense } from "@/lib/license";

export const runtime = "nodejs";

export async function GET() {
  const info = await loadLicense();
  return NextResponse.json(info);
}

export async function POST(req: NextRequest) {
  const { token } = (await req.json()) as { token?: string };
  const info = await activateLicense(token ?? "");
  return NextResponse.json(info, { status: info.valid ? 200 : 400 });
}
