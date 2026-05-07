import { NextRequest, NextResponse } from "next/server";

import {
  OAUTH_STATE_COOKIE,
  OAuthState,
  SESSION_COOKIE,
  TokenSession,
  authErrorRedirect,
  clearCookieOptions,
  oauthStateCookieOptions,
  resolveClientId,
  resolvePublicOrigin,
  sealJson,
  sessionCookieOptions,
  unsealJson
} from "../../../lib/auth-session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type TokenResponse = {
  access_token?: unknown;
  token_type?: unknown;
  expires_in?: unknown;
  scope?: unknown;
  id_token?: unknown;
};

export async function GET(request: NextRequest) {
  const sealedState = request.cookies.get(OAUTH_STATE_COOKIE)?.value;
  const oauthState = sealedState ? unsealJson<OAuthState>(sealedState) : null;
  const fallbackRedirect = "/";
  const redirectTo = oauthState?.redirectTo ?? fallbackRedirect;

  if (request.nextUrl.searchParams.get("error")) {
    return redirectWithAuthError(request, redirectTo, "openemr_authorization_denied");
  }

  const code = request.nextUrl.searchParams.get("code");
  const returnedState = request.nextUrl.searchParams.get("state");
  if (!oauthState || !code || !returnedState || returnedState !== oauthState.state) {
    // State mismatch means the callback cannot be trusted. Clear state and send
    // the user back through a fresh SMART launch instead of guessing.
    return redirectWithAuthError(request, redirectTo, "invalid_oauth_state");
  }

  if (oauthState.createdAt + 10 * 60 * 1000 < Date.now()) {
    return redirectWithAuthError(request, redirectTo, "expired_oauth_state");
  }

  try {
    const token = await exchangeCodeForToken(code, oauthState);
    const now = Date.now();
    const expiresIn = numericExpiresIn(token.expires_in);
    const accessToken = typeof token.access_token === "string" ? token.access_token : "";
    // The web layer stores the bearer in an encrypted HttpOnly cookie. Browser
    // code never reads the token directly; same-origin API proxying injects it.
    const session: TokenSession = {
      accessToken,
      tokenType: typeof token.token_type === "string" ? token.token_type : "Bearer",
      expiresAt: now + expiresIn * 1000,
      issuedAt: now,
      scope: typeof token.scope === "string" ? token.scope : undefined,
      idToken: typeof token.id_token === "string" ? token.id_token : undefined
    };

    if (!session.accessToken || session.tokenType.toLowerCase() !== "bearer") {
      return redirectWithAuthError(request, redirectTo, "invalid_token_response");
    }

    const response = NextResponse.redirect(new URL(redirectTo, resolvePublicOrigin(request)));
    response.cookies.set(SESSION_COOKIE, sealJson(session), sessionCookieOptions(expiresIn));
    response.cookies.set(OAUTH_STATE_COOKIE, "", clearCookieOptions("/api/auth"));
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    return redirectWithAuthError(request, redirectTo, "token_exchange_failed");
  }
}

async function exchangeCodeForToken(code: string, oauthState: OAuthState): Promise<TokenResponse> {
  const clientId = resolveClientId();
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: oauthState.redirectUri,
    client_id: clientId,
    code_verifier: oauthState.codeVerifier
  });

  const headers = new Headers({
    "Content-Type": "application/x-www-form-urlencoded",
    Accept: "application/json"
  });
  const clientSecret = process.env.OPENEMR_CLIENT_SECRET;
  if (clientSecret) {
    if (process.env.OPENEMR_TOKEN_AUTH_METHOD === "client_secret_basic") {
      headers.set(
        "Authorization",
        `Basic ${Buffer.from(`${clientId}:${clientSecret}`, "utf8").toString("base64")}`
      );
    } else {
      body.set("client_secret", clientSecret);
    }
  }

  const response = await fetch(oauthState.tokenEndpoint, {
    method: "POST",
    headers,
    body,
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`OpenEMR token endpoint returned ${response.status}`);
  }
  return (await response.json()) as TokenResponse;
}

function redirectWithAuthError(request: NextRequest, redirectTo: string, error: string): NextResponse {
  const response = NextResponse.redirect(
    authErrorRedirect(redirectTo, error, resolvePublicOrigin(request))
  );
  response.cookies.set(OAUTH_STATE_COOKIE, "", {
    ...oauthStateCookieOptions(),
    maxAge: 0
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}

function numericExpiresIn(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.min(Math.floor(value), 60 * 60);
  }
  return 15 * 60;
}
