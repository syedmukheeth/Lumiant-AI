import { NextResponse, type NextRequest } from "next/server";

import { buildCsp } from "@/lib/csp";

const SESSION_COOKIE = "lumiant_session";

/**
 * 1. Sets a Content-Security-Policy with a fresh per-request nonce. Next.js reads the nonce from the request's CSP
 *    header and applies it to its own scripts; pages are rendered per request so that is possible.
 * 2. Optimistic routing: sends visitors without a session cookie to /login. This is NOT an authorization layer —
 *    the API validates every request.
 */
export function proxy(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = buildCsp(nonce, process.env.NODE_ENV !== "production");

  const { pathname } = request.nextUrl;
  let response: NextResponse;
  if (pathname !== "/login" && !request.cookies.has(SESSION_COOKIE)) {
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
      source: "/((?!api|_next/static|_next/image|favicon.ico|theme-init.js).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
