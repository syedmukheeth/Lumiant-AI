"use client";

import { Moon, Sun } from "lucide-react";

/** Dark is the default; light applies only when chosen. public/theme-init.js re-applies the choice before paint. */
export function toggleTheme() {
  const root = document.documentElement;
  const next = root.dataset.theme === "light" ? "dark" : "light";
  root.dataset.theme = next;
  try {
    localStorage.setItem("lumiant-theme", next);
  } catch {
    // storage unavailable (private mode) — theme still applies for this page
  }
}

export function ThemeToggle() {
  // The icon follows the theme through CSS (`light:`), so server and client markup are identical.
  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="rounded-md p-1.5 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
      aria-label="Toggle light or dark theme"
    >
      <Sun size={16} aria-hidden className="light:hidden" />
      <Moon size={16} aria-hidden className="hidden light:block" />
    </button>
  );
}
