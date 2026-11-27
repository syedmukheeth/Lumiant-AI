"use client";

import { Boxes, MousePointerClick, Search, ShieldCheck, X } from "lucide-react";
import { useSyncExternalStore } from "react";

import { IconButton } from "@/components/ui/button";

const KEY = "lumiant-welcome-dismissed";
const EVENT = "lumiant:welcome";

const read = () => {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return true; // no storage: never nag
  }
};
const subscribe = (cb: () => void) => {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
};

const STEPS = [
  { icon: Boxes, title: "Start from the four areas", text: "Stock, replenishment, stock health and cost: each shows its figures and the questions worth asking next." },
  { icon: MousePointerClick, title: "Ask about anything you see", text: "Right-click a figure, bar or row, or press L, and the Analyst explains it with sources." },
  { icon: Search, title: "Jump anywhere", text: "Press Ctrl K to search items, open a page or type a question." },
  { icon: ShieldCheck, title: "Check every number", text: "“How this was calculated” shows the source tables, filters and your warehouse scope." },
];

/** First-run welcome on the Overview: four steps, dismissed for good in this browser. */
export function Welcome() {
  const dismissed = useSyncExternalStore(subscribe, read, () => true);
  if (dismissed) return null;
  const close = () => {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      // storage unavailable
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return (
    <section aria-label="Getting started" className="panel relative p-5 sm:p-6" data-testid="welcome">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Getting started</p>
          <h2 className="mt-1 font-display text-xl font-medium text-ink">Four things worth knowing</h2>
        </div>
        <IconButton aria-label="Dismiss getting started" onClick={close}>
          <X size={16} aria-hidden />
        </IconButton>
      </div>
      <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex gap-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-full border border-line bg-surface-2 text-ink-2">
              <s.icon size={15} aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium text-ink">
                {i + 1}. {s.title}
              </span>
              <span className="block text-xs text-ink-3">{s.text}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
