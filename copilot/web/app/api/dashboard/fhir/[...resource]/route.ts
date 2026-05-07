import { NextRequest } from "next/server";

import { readTokenSession } from "../../../../lib/auth-session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{
    resource: string[];
  }>;
};

const allowedResources = new Set([
  "Patient",
  "AllergyIntolerance",
  "Condition",
  "MedicationRequest",
  "CareTeam",
  "Observation",
  "Practitioner"
]);

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

export async function GET(request: NextRequest, context: RouteContext) {
  const session = readTokenSession(request);
  if (!session) {
    return Response.json({ error: "OpenEMR SMART session required" }, { status: 401 });
  }
  if (isCrossSiteBrowserRequest(request)) {
    return Response.json({ error: "Cross-site dashboard FHIR request rejected" }, { status: 403 });
  }

  const { resource } = await context.params;
  const [resourceType] = resource;
  if (!resourceType || !allowedResources.has(resourceType)) {
    return Response.json({ error: "FHIR resource is not allowed for dashboard rendering" }, { status: 400 });
  }

  const fhirBase = resolveFhirBaseUrl();
  if (!fhirBase) {
    return Response.json({ error: "OPENEMR_FHIR_BASE_URL or OPENEMR_BASE_URL is required" }, { status: 500 });
  }

  const upstreamPath = resource.map(encodeURIComponent).join("/");
  const upstreamUrl = new URL(upstreamPath, `${fhirBase}/`);
  upstreamUrl.search = request.nextUrl.search;

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(upstreamUrl, {
      method: "GET",
      headers: {
        Accept: "application/fhir+json, application/json",
        Authorization: `Bearer ${session.accessToken}`
      },
      cache: "no-store"
    });
  } catch {
    return Response.json(
      { error: "OpenEMR FHIR upstream is unavailable" },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }

  const responseHeaders = new Headers(upstreamResponse.headers);
  for (const header of hopByHopHeaders) {
    responseHeaders.delete(header);
  }
  responseHeaders.set("Cache-Control", "no-store");

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders
  });
}

function resolveFhirBaseUrl(): string | null {
  const configured = process.env.OPENEMR_FHIR_BASE_URL;
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const openemrBase = process.env.OPENEMR_BASE_URL;
  if (!openemrBase) {
    return null;
  }
  const site = process.env.OPENEMR_SITE ?? "default";
  return `${openemrBase.replace(/\/$/, "")}/apis/${site}/fhir`;
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
