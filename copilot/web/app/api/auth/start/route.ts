import { NextRequest, NextResponse } from "next/server";

import {
  AuthConfigError,
  OAUTH_STATE_COOKIE,
  OAuthState,
  oauthStateCookieOptions,
  pkceChallenge,
  randomUrlSafe,
  resolveClientId,
  resolvePublicOrigin,
  resolveRedirectUri,
  resolveScopes,
  resolveSmartEndpoints,
  resolveTrustedSmartUrl,
  safeRedirectTo,
  sealJson
} from "../../../lib/auth-session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  try {
    const search = request.nextUrl.searchParams;
    // The issuer/audience may arrive from OpenEMR launch context, but they are
    // still untrusted input. Resolve against the configured allowlist before
    // SMART discovery so client secrets never post to an attacker endpoint.
    const issuer = resolveTrustedSmartUrl(optionalParam(search.get("iss")), "SMART issuer");
    const audience =
      resolveTrustedSmartUrl(optionalParam(search.get("aud")), "SMART audience") ?? issuer;
    const launch = optionalParam(search.get("launch"));
    const redirectTo = safeRedirectTo(search.get("redirect_to"), resolvePublicOrigin(request));
    const endpoints = await resolveSmartEndpoints(issuer);
    const redirectUri = resolveRedirectUri(request);
    const state = randomUrlSafe(24);
    const codeVerifier = randomUrlSafe(64);

    // PKCE binds the callback to this browser-started authorization request.
    // The sealed state cookie also remembers where the user should return.
    const authUrl = new URL(endpoints.authorizationEndpoint);
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("client_id", resolveClientId());
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("scope", resolveScopes(Boolean(launch)));
    authUrl.searchParams.set("state", state);
    authUrl.searchParams.set("code_challenge", pkceChallenge(codeVerifier));
    authUrl.searchParams.set("code_challenge_method", "S256");
    if (audience) authUrl.searchParams.set("aud", audience);
    if (launch) authUrl.searchParams.set("launch", launch);

    const oauthState: OAuthState = {
      state,
      codeVerifier,
      redirectTo,
      redirectUri,
      tokenEndpoint: endpoints.tokenEndpoint,
      issuer,
      audience,
      launch,
      createdAt: Date.now()
    };

    const response = NextResponse.redirect(authUrl);
    response.cookies.set(OAUTH_STATE_COOKIE, sealJson(oauthState), oauthStateCookieOptions());
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch (error) {
    const message =
      error instanceof AuthConfigError ? error.message : "SMART authorization could not be started";
    const status =
      error instanceof AuthConfigError &&
      (message.startsWith("SMART issuer ") || message.startsWith("SMART audience "))
        ? 400
        : 500;
    return Response.json({ error: message }, { status, headers: { "Cache-Control": "no-store" } });
  }
}

function optionalParam(value: string | null): string | undefined {
  return value && value.trim() ? value.trim() : undefined;
}
