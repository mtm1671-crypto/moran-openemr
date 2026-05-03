import { NextResponse, type NextRequest } from "next/server";

export function middleware(_request: NextRequest) {
  const response = NextResponse.next();
  response.headers.set("Content-Security-Policy", contentSecurityPolicy());
  return response;
}

export const config = {
  matcher: "/:path*"
};

function contentSecurityPolicy(): string {
  const isDevelopment = process.env.NODE_ENV !== "production";
  const scriptSrc = isDevelopment
    ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    : "script-src 'self' 'unsafe-inline'";
  const connectSrc = isDevelopment
    ? "connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:* https://*.up.railway.app"
    : "connect-src 'self' https://*.up.railway.app";
  const frameAncestors = [
    "frame-ancestors",
    ...uniqueSources([
      "'self'",
      "https://*.up.railway.app",
      ...(isDevelopment ? ["http://localhost:*", "http://127.0.0.1:*"] : []),
      originSource(process.env.OPENEMR_BASE_URL),
      originSource(process.env.OPENEMR_FHIR_BASE_URL),
      ...(process.env.COPILOT_FRAME_ANCESTORS ?? "").split(/\s+/).filter(Boolean)
    ])
  ].join(" ");

  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    frameAncestors,
    "form-action 'self'",
    "img-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    scriptSrc,
    connectSrc
  ].join("; ");
}

function originSource(value: string | undefined): string | undefined {
  if (!value) return undefined;
  try {
    return new URL(value).origin;
  } catch {
    return undefined;
  }
}

function uniqueSources(sources: Array<string | undefined>): string[] {
  return [...new Set(sources.filter((source): source is string => Boolean(source)))];
}
