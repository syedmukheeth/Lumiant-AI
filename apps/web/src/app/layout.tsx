import type { Metadata } from "next";
import Script from "next/script";
import { connection } from "next/server";
import { Archivo, IBM_Plex_Mono } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

const archivo = Archivo({ subsets: ["latin"], variable: "--font-archivo", display: "swap" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
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
  return (
    <html lang="en" className={`${archivo.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh antialiased">
        <Script src="/theme-init.js" strategy="beforeInteractive" />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
