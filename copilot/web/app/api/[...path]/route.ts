import { NextRequest } from "next/server";

import { readTokenSession } from "../../lib/auth-session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const hopByHopHeaders = [
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade"
];

async function proxy(request: NextRequest, context: RouteContext) {
  const apiBase = resolveApiBaseUrl();
  if (!apiBase) {
    return Response.json(
      { error: "COPILOT_API_BASE_URL is required for the production web proxy" },
      { status: 500 }
    );
  }

  const { path } = await context.params;
  const upstreamPath = path.map(encodeURIComponent).join("/");
  const upstreamUrl = new URL(`/api/${upstreamPath}`, apiBase);
  upstreamUrl.search = request.nextUrl.search;

  const requestHeaders = new Headers(request.headers);
  for (const header of hopByHopHeaders) {
    requestHeaders.delete(header);
  }
  requestHeaders.delete("cookie");

  if (process.env.COPILOT_PROXY_ALLOW_CLIENT_AUTH !== "true") {
    requestHeaders.delete("authorization");
  }

  const session = readTokenSession(request);
  if (session) {
    if (isCrossSiteBrowserRequest(request)) {
      return Response.json({ error: "Cross-site Co-Pilot API request rejected" }, { status: 403 });
    }
    requestHeaders.set("Authorization", `Bearer ${session.accessToken}`);
  }

  const init: RequestInit = {
    method: request.method,
    headers: requestHeaders,
    redirect: "manual",
    cache: "no-store"
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.arrayBuffer();
    if (body.byteLength > 0) {
      init.body = body;
    }
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(upstreamUrl, init);
  } catch {
    return Response.json(
      { error: "Co-Pilot API upstream is unavailable" },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
  const responseHeaders = new Headers(upstreamResponse.headers);
  for (const header of hopByHopHeaders) {
    responseHeaders.delete(header);
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;

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

function isCrossSiteBrowserRequest(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (origin && !allowedBrowserOrigins(request).has(origin)) {
    return true;
  }

  const fetchSite = request.headers.get("sec-fetch-site");
  return fetchSite === "cross-site";
}

function allowedBrowserOrigins(request: NextRequest): Set<string> {
  const origins = new Set<string>([request.nextUrl.origin]);
  addOrigin(origins, process.env.PUBLIC_BASE_URL);

  const forwardedHost = firstHeaderValue(
    request.headers.get("x-forwarded-host") ?? request.headers.get("host")
  );
  if (forwardedHost) {
    const forwardedProto = firstHeaderValue(request.headers.get("x-forwarded-proto")) ?? "https";
    addOrigin(origins, `${forwardedProto}://${forwardedHost}`);
    addOrigin(origins, `https://${forwardedHost}`);
  }

  return origins;
}

function firstHeaderValue(value: string | null): string | null {
  return value?.split(",")[0]?.trim() || null;
}

function addOrigin(origins: Set<string>, value: string | undefined): void {
  if (!value) return;
  try {
    origins.add(new URL(value).origin);
  } catch {
    // Ignore invalid deployment metadata and keep the stricter origin set.
  }
}
