/** Unmissable label: demo data is generated, never customer data (brief §3.2, §21). */
export function SyntheticTape({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="tape inline-flex shrink-0 items-center rounded-[3px] p-[3px]"
      title="Generated demonstration data — not from any customer system"
      data-testid="synthetic-badge"
    >
      <span className="tape-label whitespace-nowrap rounded-[2px] px-1.5 py-0.5 text-[0.625rem] font-extrabold tracking-[0.14em]">
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
