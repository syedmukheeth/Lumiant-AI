import type { NextConfig } from "next";

// FastAPI origin. Browser traffic stays same-origin: /api/* is proxied here, so the httpOnly session
// cookie set by the API works without CORS. Evaluated at build time for `next build`.
const API_ORIGIN = process.env.LUMIANT_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The dev-only route indicator sat over "Sign out" at the bottom of the nav rail, and every other corner holds a
  // control (theme toggle, Analyst dock). Errors still open Next's overlay in development; production never shows it.
  devIndicators: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  // The Content-Security-Policy (with a per-request nonce) is set in src/proxy.ts.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
