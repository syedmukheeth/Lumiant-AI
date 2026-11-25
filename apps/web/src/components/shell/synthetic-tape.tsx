import type { DataClassification } from "@/lib/api";

/** Plain, always-visible label: demo data is generated, never customer data (brief §3.2, §21). */
export function SyntheticTape({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-full border border-line-strong bg-surface-2 px-2 py-0.5"
      title="Generated demonstration data, not from any customer system"
      data-testid="synthetic-badge"
    >
      <span className="whitespace-nowrap text-[0.625rem] leading-4 font-semibold tracking-[0.08em] text-ink-2">
        {compact ? (
          "SYNTHETIC"
        ) : (
          <>
            <span className="sm:hidden">SYNTHETIC</span>
            <span className="hidden sm:inline">SYNTHETIC DEMO DATA</span>
          </>
        )}
      </span>
    </span>
  );
}

/** Real client files loaded on this machine for analysis (ADR-0008): confidential, never shared or deployed. */
export function ClientExtractTape({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-full border border-signal bg-signal-soft px-2 py-0.5"
      title="Real client data loaded locally from exported files. Confidential: do not share or deploy"
      data-testid="client-extract-badge"
    >
      <span className="whitespace-nowrap text-[0.625rem] leading-4 font-bold tracking-[0.08em] text-signal">
        {compact ? (
          "CLIENT EXTRACT"
        ) : (
          <>
            <span className="sm:hidden">CLIENT EXTRACT</span>
            <span className="hidden sm:inline">CLIENT EXTRACT · CONFIDENTIAL · LOCAL</span>
          </>
        )}
      </span>
    </span>
  );
}

/** The label for the data a tenant serves: client-extract badge, synthetic tape, or nothing for live customer data. */
export function DataBadge({
  classification,
  synthetic,
  compact = false,
}: {
  classification?: DataClassification;
  synthetic: boolean;
  compact?: boolean;
}) {
  if (classification === "customer_extract") return <ClientExtractTape compact={compact} />;
  if (synthetic) return <SyntheticTape compact={compact} />;
  return null;
}
