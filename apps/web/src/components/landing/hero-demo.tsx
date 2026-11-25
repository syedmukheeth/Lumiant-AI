"use client";

import { CheckCircle2, MessageSquareText, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { KpiCard } from "@/components/viz/kpi-card";
import { SAMPLE_SPARK } from "@/components/viz/samples";

const QUESTION = "Which items hold most of our value in Riyadh, and are any of them dormant?";
const ANSWER =
  "Eight items hold 80% of the value in warehouse 3100. Two of them have had no issue movement for more than 270 days: Item 101 and Item 108.";
const STEPS = ["Understanding the question", "Querying the inventory data", "Scanning movement history", "Checking every number against the results"];

/**
 * The hero's product frame: a sample Analyst exchange that types itself out once. Sample values only (labelled);
 * with reduced motion the finished state shows at once.
 */
export function HeroDemo() {
  const [chars, setChars] = useState(0);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setStep(STEPS.length);
      setChars(ANSWER.length);
      return;
    }
    const timers: number[] = [];
    STEPS.forEach((_, i) => timers.push(window.setTimeout(() => setStep(i + 1), 500 + i * 450)));
    const start = 500 + STEPS.length * 450;
    const typer = window.setTimeout(function tick() {
      setChars((c) => {
        if (c >= ANSWER.length) return c;
        timers.push(window.setTimeout(tick, 14));
        return c + 2;
      });
    }, start);
    timers.push(typer);
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, []);

  const done = chars >= ANSWER.length;
  return (
    <div className="relative" aria-label="Sample product view with sample data" role="group">
      <div className="panel overflow-hidden shadow-e3">
        <div className="flex items-center gap-2 border-b border-line bg-surface-2 px-4 py-2.5">
          <span className="size-2.5 rounded-full bg-line-strong" aria-hidden />
          <span className="size-2.5 rounded-full bg-line-strong" aria-hidden />
          <span className="size-2.5 rounded-full bg-line-strong" aria-hidden />
          <span className="ml-3 text-caption text-ink-3">Lumiant · Command centre</span>
          <span className="ml-auto rounded-full border border-signal/35 bg-signal-soft px-2 py-0.5 text-caption font-medium text-signal">Sample data</span>
        </div>
        <div className="grid gap-3 p-4 sm:grid-cols-2">
          <KpiCard label="Inventory value" value="USD 2.77M" trend={SAMPLE_SPARK} delta={{ direction: "up", text: "1.5%", goodWhen: "down", period: "vs Oct" }} />
          <KpiCard label="Below reorder" value="18" unit="items" trend={[24, 22, 25, 21, 19, 20, 18]} tone="critical" delta={{ direction: "down", text: "2", goodWhen: "down", period: "vs last week" }} />
        </div>
        <div className="border-t border-line p-4">
          <div className="ml-auto w-fit max-w-[85%] rounded-panel rounded-br-sm bg-accent px-3 py-2 text-sm text-accent-ink">{QUESTION}</div>
          <div className="mt-3 rounded-panel border border-line bg-surface-2 p-3">
            <p className="mb-2 flex items-center gap-1.5 text-caption font-medium text-ink-2">
              <MessageSquareText className="size-3.5 text-accent" aria-hidden /> Lumiant Analyst
            </p>
            <ul className="mb-2 space-y-1">
              {STEPS.map((s, i) => (
                <li key={s} className={`flex items-center gap-1.5 text-caption transition-opacity ${i < step ? "text-ink-2 opacity-100" : "opacity-0"}`}>
                  {i === STEPS.length - 1 ? <ShieldCheck className="size-3.5 text-ok" aria-hidden /> : <CheckCircle2 className="size-3.5 text-ok" aria-hidden />}
                  {s}
                </li>
              ))}
            </ul>
            <p className="min-h-[3.75rem] text-sm leading-relaxed text-ink" aria-hidden>
              {ANSWER.slice(0, chars)}
              {!done && step >= STEPS.length && <span className="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 animate-pulse bg-accent" aria-hidden />}
            </p>
            <p className="sr-only">{ANSWER}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
