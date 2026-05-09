const API_PREFIX = "/api/";
const VIEWER_PREFIX = "/evidence/";
const ALLOWED_API_PREFIXES = ["/api/source/", "/api/documents/"];

export function evidenceViewerHref(sourceUrl: string | null | undefined): string | undefined {
  if (!sourceUrl?.startsWith(API_PREFIX)) return undefined;
  const { pathname, search } = splitPathAndSearch(sourceUrl);
  if (!isAllowedEvidenceApiPath(pathname)) return undefined;
  return `${VIEWER_PREFIX}${pathname.slice(API_PREFIX.length)}${search}`;
}

export function evidenceApiHrefFromViewerLocation(
  pathname: string,
  search: string
): string | undefined {
  const viewerIndex = pathname.indexOf(VIEWER_PREFIX);
  if (viewerIndex < 0) return undefined;
  const sourcePath = pathname.slice(viewerIndex + VIEWER_PREFIX.length);
  if (!sourcePath) return undefined;
  const apiPath = `${API_PREFIX}${sourcePath}`;
  if (!isAllowedEvidenceApiPath(apiPath)) return undefined;
  return `${apiPath}${search}`;
}

function splitPathAndSearch(value: string): { pathname: string; search: string } {
  const hashIndex = value.indexOf("#");
  const withoutHash = hashIndex >= 0 ? value.slice(0, hashIndex) : value;
  const queryIndex = withoutHash.indexOf("?");
  if (queryIndex < 0) {
    return { pathname: withoutHash, search: "" };
  }
  return {
    pathname: withoutHash.slice(0, queryIndex),
    search: withoutHash.slice(queryIndex)
  };
}

function isAllowedEvidenceApiPath(pathname: string): boolean {
  return ALLOWED_API_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}
