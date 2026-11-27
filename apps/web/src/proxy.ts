import { NextResponse, type NextRequest } from "next/server";

import { buildCsp } from "@/lib/csp";

const SESSION_COOKIE = "lumiant_session";
/** Pages anyone may open: the public landing page and the sign-in page. Neither reads tenant data. */
const PUBLIC_PAGES = new Set(["/", "/login"]);

/**
 * Whether a page request should be sent to the development sign-in page.
 *
 * Only in development auth (`LUMIANT_AUTH_MODE` unset or `dev`): a visitor without the dev session cookie goes to
 * /login. In `oidc` mode the customer's identity-aware gateway (e.g. oauth2-proxy in front of web and API) signs the
 * user in and forwards `Authorization: Bearer …`, so there is no dev cookie to look for and redirecting would lock every
 * user out (docs/PRODUCTION_AUTHENTICATION.md, LA-01). Either way this is routing, not authorization: the API
 * authenticates and authorizes every request.
 */
export function needsDevLogin(pathname: string, hasSessionCookie: boolean, authMode: string | undefined): boolean {
  if ((authMode ?? "dev").toLowerCase() === "oidc") return false;
  return !PUBLIC_PAGES.has(pathname) && !hasSessionCookie;
}

/**
 * 1. Sets a Content-Security-Policy with a fresh per-request nonce. Next.js reads the nonce from the request's CSP
 *    header and applies it to its own scripts; pages are rendered per request so that is possible.
 * 2. Optimistic routing in development auth: see `needsDevLogin`.
 */
export function proxy(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = buildCsp(nonce, process.env.NODE_ENV !== "production");

  const { pathname } = request.nextUrl;
  let response: NextResponse;
  if (needsDevLogin(pathname, request.cookies.has(SESSION_COOKIE), process.env.LUMIANT_AUTH_MODE)) {
    response = NextResponse.redirect(new URL("/login", request.url));
  } else {
    const headers = new Headers(request.headers);
    headers.set("x-nonce", nonce);
    headers.set("Content-Security-Policy", csp);
    response = NextResponse.next({ request: { headers } });
  }
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      // Public static files (logo on the sign-in page, theme script) must load without a session.
      source: "/((?!api|_next/static|_next/image|favicon.ico|theme-init.js|brand/).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
