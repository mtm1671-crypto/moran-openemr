export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const apiBase = resolveApiBaseUrl();
  if (!apiBase) {
    return Response.json(
      { error: "COPILOT_API_BASE_URL is required for the readiness proxy" },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(`${apiBase}/readyz`, {
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
  } catch {
    return Response.json(
      { error: "Co-Pilot API readiness endpoint is unavailable" },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }

  const body = await upstreamResponse.text();
  return new Response(body, {
    status: upstreamResponse.status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": upstreamResponse.headers.get("content-type") ?? "application/json"
    }
  });
}

function resolveApiBaseUrl() {
  const configured = process.env.COPILOT_API_BASE_URL ?? process.env.API_BASE_URL;
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "production") {
    return null;
  }
  return "http://127.0.0.1:8001";
}
