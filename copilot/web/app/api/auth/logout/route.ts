import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE, clearCookieOptions, resolvePublicOrigin } from "../../../lib/auth-session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/", resolvePublicOrigin(request)));
  response.cookies.set(SESSION_COOKIE, "", clearCookieOptions());
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, "", clearCookieOptions());
  response.headers.set("Cache-Control", "no-store");
  return response;
}
