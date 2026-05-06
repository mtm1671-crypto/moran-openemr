import crypto from "node:crypto";

import type { NextRequest } from "next/server";

export const SESSION_COOKIE = "copilot_session";
export const OAUTH_STATE_COOKIE = "copilot_oauth_state";

const SESSION_MAX_AGE_SECONDS = 60 * 60;
const OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60;
const CLOCK_SKEW_SECONDS = 30;

export type TokenSession = {
  accessToken: string;
  tokenType: string;
  expiresAt: number;
  issuedAt: number;
  scope?: string;
  idToken?: string;
};

export type OAuthState = {
  state: string;
  codeVerifier: string;
  redirectTo: string;
  redirectUri: string;
  tokenEndpoint: string;
  issuer?: string;
  audience?: string;
  launch?: string;
  createdAt: number;
};

export type SmartEndpoints = {
  authorizationEndpoint: string;
  tokenEndpoint: string;
};

type CookieOptions = {
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax" | "strict" | "none";
  path: string;
  maxAge: number;
};

type SmartConfiguration = {
  authorization_endpoint?: unknown;
  token_endpoint?: unknown;
};

export class AuthConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthConfigError";
  }
}

export function readTokenSession(request: NextRequest): TokenSession | null {
  const sealed = request.cookies.get(SESSION_COOKIE)?.value;
  if (!sealed) return null;

  const session = unsealJson<TokenSession>(sealed);
  if (!session || !isTokenSessionValid(session)) {
    return null;
  }
  return session;
}

export function isTokenSessionValid(session: TokenSession): boolean {
  return Boolean(
    session.accessToken &&
      session.tokenType.toLowerCase() === "bearer" &&
      session.expiresAt - CLOCK_SKEW_SECONDS * 1000 > Date.now()
  );
}

export function sealJson(value: unknown): string {
  const key = sessionSecretKey();
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
  const plaintext = Buffer.from(JSON.stringify(value), "utf8");
  const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return [
    "v1",
    iv.toString("base64url"),
    tag.toString("base64url"),
    encrypted.toString("base64url")
  ].join(".");
}

export function unsealJson<T>(sealed: string): T | null {
  try {
    const [version, ivValue, tagValue, encryptedValue] = sealed.split(".");
    if (version !== "v1" || !ivValue || !tagValue || !encryptedValue) {
      return null;
    }

    const decipher = crypto.createDecipheriv(
      "aes-256-gcm",
      sessionSecretKey(),
      Buffer.from(ivValue, "base64url")
    );
    decipher.setAuthTag(Buffer.from(tagValue, "base64url"));
    const plaintext = Buffer.concat([
      decipher.update(Buffer.from(encryptedValue, "base64url")),
      decipher.final()
    ]);
    return JSON.parse(plaintext.toString("utf8")) as T;
  } catch {
    return null;
  }
}

export function sessionCookieOptions(maxAge = SESSION_MAX_AGE_SECONDS): CookieOptions {
  return {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: cookieSameSite(),
    path: "/",
    maxAge
  };
}

export function oauthStateCookieOptions(): CookieOptions {
  return {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: cookieSameSite(),
    path: "/api/auth",
    maxAge: OAUTH_STATE_MAX_AGE_SECONDS
  };
}

export function clearCookieOptions(path = "/"): CookieOptions {
  return {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: cookieSameSite(),
    path,
    maxAge: 0
  };
}

export function randomUrlSafe(bytes = 32): string {
  return crypto.randomBytes(bytes).toString("base64url");
}

export function pkceChallenge(verifier: string): string {
  return crypto.createHash("sha256").update(verifier).digest("base64url");
}

export function resolveRedirectUri(request: NextRequest): string {
  const configured = process.env.COPILOT_OAUTH_REDIRECT_URI ?? process.env.OPENEMR_REDIRECT_URI;
  if (configured) return configured;

  const publicBase = (process.env.PUBLIC_BASE_URL ?? request.nextUrl.origin).replace(/\/$/, "");
  return `${publicBase}/api/auth/callback`;
}

export function resolvePublicOrigin(request: NextRequest): string {
  const publicBase = process.env.PUBLIC_BASE_URL;
  if (publicBase) {
    return new URL(publicBase).origin;
  }
  return request.nextUrl.origin;
}

export function resolveClientId(): string {
  const clientId = process.env.OPENEMR_CLIENT_ID;
  if (!clientId) {
    throw new AuthConfigError("OPENEMR_CLIENT_ID is required for SMART authorization");
  }
  return clientId;
}

export function resolveScopes(hasLaunchContext: boolean): string {
  const configured = process.env.OPENEMR_SCOPES;
  const defaultScopes = [
    "openid",
    "api:oemr",
    "api:fhir",
    "fhirUser",
    "user/Patient.read",
    "user/Practitioner.read",
    "user/Observation.read",
    "user/Observation.write",
    "user/Condition.read",
    "user/MedicationRequest.read",
    "user/AllergyIntolerance.read",
    "user/DocumentReference.read"
  ];
  const scopes = new Set((configured ?? defaultScopes.join(" ")).split(/\s+/).filter(Boolean));
  if (hasLaunchContext) {
    scopes.add("launch");
  }
  return [...scopes].join(" ");
}

export function resolveTrustedSmartUrl(value: string | undefined, label: string): string | undefined {
  if (!value) return undefined;

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new AuthConfigError(`${label} must be a valid URL`);
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new AuthConfigError(`${label} must use http or https`);
  }

  const allowedOrigins = resolveAllowedOpenEmrOrigins();
  if (allowedOrigins.size === 0) {
    throw new AuthConfigError("OPENEMR_BASE_URL is required to validate SMART launch URLs");
  }

  if (!allowedOrigins.has(url.origin)) {
    throw new AuthConfigError(`${label} is not an allowed OpenEMR origin`);
  }

  return url.toString().replace(/\/$/, "");
}

export async function resolveSmartEndpoints(issuer?: string): Promise<SmartEndpoints> {
  const explicitAuthorization =
    process.env.OPENEMR_AUTHORIZATION_URL ?? process.env.COPILOT_OPENEMR_AUTHORIZATION_URL;
  const explicitToken =
    process.env.OPENEMR_TOKEN_URL ??
    process.env.OPENEMR_OAUTH_TOKEN_URL ??
    process.env.COPILOT_OPENEMR_TOKEN_URL;

  if (explicitAuthorization && explicitToken) {
    return {
      authorizationEndpoint: explicitAuthorization,
      tokenEndpoint: explicitToken
    };
  }

  if (issuer) {
    const discovered = await discoverSmartEndpoints(issuer);
    if (discovered) {
      return {
        authorizationEndpoint: explicitAuthorization ?? discovered.authorizationEndpoint,
        tokenEndpoint: explicitToken ?? discovered.tokenEndpoint
      };
    }
  }

  const authBase = resolveAuthBase(issuer);
  return {
    authorizationEndpoint: explicitAuthorization ?? `${authBase}/authorize`,
    tokenEndpoint: explicitToken ?? `${authBase}/token`
  };
}

export function safeRedirectTo(value: string | null, origin: string): string {
  if (!value) return "/";

  try {
    const url = new URL(value, origin);
    if (url.origin !== origin || url.pathname.startsWith("/api/auth/")) {
      return "/";
    }
    return `${url.pathname}${url.search}`;
  } catch {
    return "/";
  }
}

export function authErrorRedirect(redirectTo: string, error: string, origin: string): URL {
  const url = new URL(redirectTo, origin);
  url.searchParams.set("auth_error", error);
  return url;
}

function sessionSecretKey(): Buffer {
  const secret =
    process.env.COPILOT_SESSION_SECRET ??
    process.env.AUTH_SECRET ??
    process.env.NEXTAUTH_SECRET ??
    "";
  if (Buffer.byteLength(secret, "utf8") < 32) {
    throw new AuthConfigError("COPILOT_SESSION_SECRET must be at least 32 bytes");
  }
  return crypto.createHash("sha256").update(secret, "utf8").digest();
}

function cookieSecure(): boolean {
  const sameSite = cookieSameSite();
  if (sameSite === "none") return true;
  if (process.env.COPILOT_COOKIE_SECURE === "false") return false;
  return process.env.NODE_ENV === "production" || process.env.COPILOT_COOKIE_SECURE === "true";
}

function cookieSameSite(): "lax" | "strict" | "none" {
  const configured = process.env.COPILOT_COOKIE_SAMESITE?.toLowerCase();
  if (configured === "strict" || configured === "none") return configured;
  return "lax";
}

function resolveAllowedOpenEmrOrigins(): Set<string> {
  const candidates = [
    process.env.OPENEMR_BASE_URL,
    process.env.OPENEMR_FHIR_BASE_URL,
    process.env.OPENEMR_AUTH_BASE_URL,
    process.env.COPILOT_OPENEMR_AUTH_BASE_URL,
    process.env.OPENEMR_AUTHORIZATION_URL,
    process.env.COPILOT_OPENEMR_AUTHORIZATION_URL,
    process.env.OPENEMR_TOKEN_URL,
    process.env.OPENEMR_OAUTH_TOKEN_URL,
    process.env.COPILOT_OPENEMR_TOKEN_URL
  ];
  const origins = new Set<string>();
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      origins.add(new URL(candidate).origin);
    } catch {
      continue;
    }
  }
  return origins;
}

async function discoverSmartEndpoints(issuer: string): Promise<SmartEndpoints | null> {
  try {
    const discoveryUrl = new URL(`${issuer.replace(/\/$/, "")}/.well-known/smart-configuration`);
    const response = await fetch(discoveryUrl, { cache: "no-store" });
    if (!response.ok) return null;

    const config = (await response.json()) as SmartConfiguration;
    if (
      typeof config.authorization_endpoint === "string" &&
      typeof config.token_endpoint === "string"
    ) {
      return {
        authorizationEndpoint: config.authorization_endpoint,
        tokenEndpoint: config.token_endpoint
      };
    }
  } catch {
    return null;
  }
  return null;
}

function resolveAuthBase(issuer?: string): string {
  const base =
    process.env.OPENEMR_AUTH_BASE_URL ??
    process.env.COPILOT_OPENEMR_AUTH_BASE_URL ??
    process.env.OPENEMR_BASE_URL ??
    issuer;
  if (!base) {
    throw new AuthConfigError(
      "OPENEMR_AUTH_BASE_URL or OPENEMR_BASE_URL is required when SMART discovery is unavailable"
    );
  }

  const trimmed = base.replace(/\/$/, "");
  if (/\/oauth2\/[^/]+$/.test(new URL(trimmed).pathname)) {
    return trimmed;
  }

  const site = process.env.OPENEMR_SITE ?? "default";
  return `${trimmed}/oauth2/${site}`;
}
