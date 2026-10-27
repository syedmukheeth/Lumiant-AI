"use client";

import { SunMoon } from "lucide-react";

export function ThemeToggle() {
  const toggle = () => {
    const root = document.documentElement;
    const current =
      root.dataset.theme ?? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try {
      localStorage.setItem("lumiant-theme", next);
    } catch {
      // storage unavailable (private mode) — theme still applies for this page
    }
  };
  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-sm p-1.5 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
      aria-label="Toggle light or dark theme"
    >
      <SunMoon size={16} aria-hidden />
    </button>
  );
}
