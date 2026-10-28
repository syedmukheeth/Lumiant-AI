"use client";

import { useSyncExternalStore } from "react";

// The rail state lives on <html data-rail> (applied before first paint by public/theme-init.js) so the layout never
// shifts on hydration; this module is the only writer.
const EVENT = "lumiant:rail";
const KEY = "lumiant-rail";

export const isRailCollapsed = () => document.documentElement.dataset.rail === "collapsed";

export function toggleRail() {
  const root = document.documentElement;
  const collapse = !isRailCollapsed();
  if (collapse) root.dataset.rail = "collapsed";
  else delete root.dataset.rail;
  try {
    localStorage.setItem(KEY, collapse ? "collapsed" : "expanded");
  } catch {
    // storage unavailable (private mode): the state still applies to this page
  }
  window.dispatchEvent(new Event(EVENT));
}

const subscribe = (onChange: () => void) => {
  window.addEventListener(EVENT, onChange);
  return () => window.removeEventListener(EVENT, onChange);
};

export const useRailCollapsed = () => useSyncExternalStore(subscribe, isRailCollapsed, () => false);
