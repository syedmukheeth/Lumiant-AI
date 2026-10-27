import type { Metadata } from "next";
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

// Applies a saved theme before first paint (no flash). Static string, no user input.
const THEME_SCRIPT = `try{var t=localStorage.getItem("lumiant-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${archivo.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-dvh antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
