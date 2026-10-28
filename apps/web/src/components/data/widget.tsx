"use client";

import { AlertTriangle, Lock, ServerCrash } from "lucide-react";
import { clsx } from "clsx";

import { AnalyzeButton, analyzableProps } from "@/components/analyst/analyzable";
import { analyze as analyzeSelection } from "@/components/analyst/store";
import { ProvenanceButton } from "@/components/data/provenance";
import type { Selection } from "@/lib/agent";
import { ApiError, type Provenance, type ResultWarning } from "@/lib/api";

export function Warnings({ warnings }: { warnings?: ResultWarning[] }) {
  if (!warnings?.length) return null;
  return (
    <ul className="mt-3 space-y-1.5">
      {warnings.map((w) => (
        <li key={w.code} className="flex items-start gap-1.5 rounded-md bg-signal-soft/60 px-2 py-1.5 text-xs text-ink-2">
          <AlertTriangle size={13} className="mt-px shrink-0 text-signal" aria-hidden />
          <span>{w.message}</span>
        </li>
      ))}
    </ul>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : null;
  const forbidden = e?.status === 403;
  const Icon = forbidden ? Lock : ServerCrash;
  return (
    <div role="status" className="flex h-full min-h-24 flex-col items-start justify-center gap-1 text-sm">
      <span className="flex items-center gap-1.5 font-medium text-ink">
        <Icon size={15} className={forbidden ? "text-ink-3" : "text-signal"} aria-hidden />
        {forbidden ? "Not available for your role" : "Could not load this"}
      </span>
      <span className="text-xs text-ink-3">
        {e?.message ?? "Unexpected error."}
        {e?.requestId && <span className="figure"> · ref {e.requestId.slice(0, 12)}</span>}
      </span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton rounded-md", className)} aria-hidden />;
}

export function Panel({
  title,
  subtitle,
  provenance,
  warnings,
  actions,
  children,
  className,
  style,
  analyze,
}: {
  title: string;
  subtitle?: string;
  provenance?: Provenance;
  warnings?: ResultWarning[];
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  /** Makes the whole panel something the Analyst can be pointed at (right-click, spark button, Lens). */
  analyze?: Selection;
}) {
  return (
    <section
      className={clsx("rise panel flex min-w-0 flex-col p-4 transition-colors hover:border-line-strong sm:p-5", className)}
      style={style}
      aria-label={title}
      {...(analyze ? analyzableProps(analyze) : {})}
      onContextMenu={
        analyze
          ? (e) => {
              if (e.shiftKey || (e.target as Element).closest("[data-analyzable]") !== e.currentTarget) return;
              e.preventDefault();
              analyzeSelection(analyze);
            }
          : undefined
      }
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[0.9375rem] font-semibold tracking-tight text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {actions}
          {analyze && <AnalyzeButton sel={analyze} />}
          <ProvenanceButton provenance={provenance} />
        </div>
      </header>
      <div className="min-h-0 flex-1">{children}</div>
      <Warnings warnings={warnings} />
    </section>
  );
}
