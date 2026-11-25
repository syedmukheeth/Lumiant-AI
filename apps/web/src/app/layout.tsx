import type { Metadata } from "next";
import Script from "next/script";
import { headers } from "next/headers";
import { connection } from "next/server";
import localFont from "next/font/local";
import { GeistMono } from "geist/font/mono";

import { Providers } from "@/components/providers";

import "./globals.css";

// Inter (variable, with the optical-size axis) for all text and numbers; Geist Mono only for identifiers. Both are
// woff2 files shipped in npm packages and served from /_next/static: no font CDN at build or run time, so the CSP
// keeps font-src 'self'.
const inter = localFont({
  src: "../../node_modules/inter-ui/variable/InterVariable.woff2",
  variable: "--font-inter",
  weight: "100 900",
  display: "swap",
});

// Newsreader (SIL OFL) for page titles and marketing headlines: an editorial serif beside Inter's UI text.
const newsreader = localFont({
  src: "../../node_modules/@fontsource-variable/newsreader/files/newsreader-latin-standard-normal.woff2",
  variable: "--font-newsreader",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Lumiant Inventory Intelligence", template: "%s · Lumiant" },
  description: "Inventory intelligence on top of your existing data warehouse.",
  robots: { index: false, follow: false },
};

// Every page is rendered per request: the CSP nonce (src/proxy.ts) only exists at request time, and Next.js can
// only put it on its own inline scripts when it renders the page for that request. Prerendered shells cannot be nonced.
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  await connection();
  // Next.js nonces this script on the server; passing the same nonce as a prop keeps the client render identical, so
  // hydration does not report a nonce mismatch.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang="en" className={`${inter.variable} ${newsreader.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh antialiased">
        <Script src="/theme-init.js" strategy="beforeInteractive" nonce={nonce} />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
