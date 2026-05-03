import { NextRequest } from "next/server";

import { readTokenSession } from "../../../lib/auth-session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const session = readTokenSession(request);
  return Response.json(
    {
      authenticated: Boolean(session),
      expires_at: session ? new Date(session.expiresAt).toISOString() : null,
      scope: session?.scope ?? null
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}
