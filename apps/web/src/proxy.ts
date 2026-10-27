import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "lumiant_session";

/**
 * Optimistic routing only: sends visitors without a session cookie to /login.
 * It is NOT an authorization layer — the API validates every request.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname === "/login") return NextResponse.next();
  if (!request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
