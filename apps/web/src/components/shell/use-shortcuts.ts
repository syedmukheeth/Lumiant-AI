"use client";

import { useEffect, useRef } from "react";

import type { NavItem } from "@/components/shell/nav";

/** Time window for the second key of a "G then key" chord. */
const CHORD_MS = 1200;

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

type Handlers = {
  nav: readonly NavItem[];
  onPalette: () => void;
  onNavigate: (href: string) => void;
  onToggleRail: () => void;
  /** Analyst dock (⌘J / Ctrl+J) and Lens mode (L); omitted when the user cannot chat. */
  onDock?: () => void;
  onLens?: () => void;
};

/**
 * App-wide keyboard shortcuts: ⌘K / Ctrl+K (anywhere) and "/" open the command palette, ⌘J / Ctrl+J toggles the
 * Analyst, "L" toggles Lens mode, "G then key" jumps to a page, "[" collapses the rail. Single keys never fire while
 * the user is typing or holding a modifier.
 */
export function useShortcuts(handlers: Handlers) {
  const live = useRef(handlers);
  useEffect(() => {
    live.current = handlers;
  });

  useEffect(() => {
    let chordAt = 0;
    const onKey = (e: KeyboardEvent) => {
      const h = live.current;
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        h.onPalette();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "j" && h.onDock) {
        e.preventDefault();
        h.onDock();
        return;
      }
      if (e.defaultPrevented || e.repeat || e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      const key = e.key.toLowerCase();
      if (chordAt && Date.now() - chordAt < CHORD_MS) {
        chordAt = 0;
        const item = h.nav.find((n) => n.key === key);
        if (item) {
          e.preventDefault();
          h.onNavigate(item.href);
        }
        return;
      }
      chordAt = 0;
      if (key === "g") chordAt = Date.now();
      else if (key === "/") {
        e.preventDefault();
        h.onPalette();
      } else if (key === "[") {
        e.preventDefault();
        h.onToggleRail();
      } else if (key === "l" && h.onLens) {
        e.preventDefault();
        h.onLens();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
