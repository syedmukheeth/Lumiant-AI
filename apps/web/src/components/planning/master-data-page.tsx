"use client";

import { useState } from "react";

import { Qty, RecommendationNote } from "@/components/planning/shared";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import type { DuplicateFinding } from "@/lib/api";
import { formatCount, humanize } from "@/lib/format";
import { useDuplicates, useLifecycle } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

const TABS = [
  { id: "duplicates", label: "Duplicate items", blurb: "Item records that may describe the same product. Matched on normalised description, manufacturer part number and specifications; nothing is merged." },
  { id: "lifecycle", label: "Lifecycle review", blurb: "Which stock is still needed. An item is never called obsolete from inactivity alone: criticality, BOM use, open demand and supersession are checked." },
] as const;
type Tab = (typeof TABS)[number]["id"];

const VERDICT: Record<DuplicateFinding["verdict"], { label: string; tone: "signal" | "accent" | "neutral" }> = {
  probable_duplicate: { label: "Probable duplicate", tone: "signal" },
  conflict: { label: "Conflicting records", tone: "signal" },
  possible_duplicate: { label: "Possible duplicate", tone: "accent" },
  different_specification: { label: "Different specification", tone: "neutral" },
};

function DuplicatesView() {
  const { data, error, isPending } = useDuplicates();
  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error) return <Panel title="Duplicate items"><ErrorState error={error} /></Panel>;
  return (
    <Panel title="Pairs to review" subtitle={`${formatCount(data.findings.length)} ${data.findings.length === 1 ? "pair" : "pairs"} in the item master`}>
      {data.findings.length === 0 ? (
        <p className="text-sm text-ink-3">No probable or possible duplicates found.</p>
      ) : (
        <ul className="divide-y divide-line">
          {data.findings.map((f) => (
            <li key={`${f.item_a}-${f.item_b}`} className="py-3" data-testid={`dup-${f.item_a}-${f.item_b}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="code text-sm text-ink">{f.item_a}</span>
                <span className="text-ink-3">and</span>
                <span className="code text-sm text-ink">{f.item_b}</span>
                <Badge tone={VERDICT[f.verdict].tone}>{VERDICT[f.verdict].label}</Badge>
                <span className="text-xs text-ink-3">{f.confidence} confidence · {Math.round(f.similarity * 100)}% similar</span>
              </div>
              <p className="mt-1 text-xs text-ink-2">{f.reasons.join("; ")}</p>
              <p className="mt-0.5 text-xs text-ink-3">{f.action}</p>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3"><RecommendationNote>Review only: records are never merged, renamed or deleted automatically; BOM references stay intact.</RecommendationNote></div>
    </Panel>
  );
}

const LIFE_TONE: Record<string, "signal" | "accent" | "neutral" | "ok"> = {
  obsolete_candidate: "signal",
  expiring_action: "signal",
  superseded_run_down: "accent",
  slow_moving_review: "accent",
  critical_keep: "ok",
  active: "neutral",
};

function LifecycleView() {
  const { data, error, isPending } = useLifecycle();
  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error) return <Panel title="Lifecycle review"><ErrorState error={error} /></Panel>;
  const order = ["obsolete_candidate", "expiring_action", "superseded_run_down", "slow_moving_review", "critical_keep", "active"];
  const findings = [...data.findings].sort((a, b) => order.indexOf(a.verdict) - order.indexOf(b.verdict));
  return (
    <Panel title="Items with stock" subtitle={`reviewed on ${data.today}`}>
      <ul className="divide-y divide-line">
        {findings.map((f) => (
          <li key={f.item_id} className="py-3" data-testid={`life-${f.item_id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="code text-sm text-ink">{f.item_id}</span>
              <Badge tone={LIFE_TONE[f.verdict] ?? "neutral"}>{humanize(f.verdict)}</Badge>
              <span className="ml-auto text-xs text-ink-3">on hand <Qty value={f.on_hand} /></span>
            </div>
            <p className="mt-1 text-xs text-ink-2">{f.evidence.join(" · ")}</p>
            <p className="mt-0.5 text-xs text-ink-3">
              {f.action}
              {f.possible_excess && f.possible_excess !== "0" ? ` Possible excess: ${f.possible_excess}.` : ""}
            </p>
          </li>
        ))}
      </ul>
      <div className="mt-3"><RecommendationNote>An authorised user decides: nothing is blocked or disposed of automatically.</RecommendationNote></div>
    </Panel>
  );
}

export function MasterDataPage() {
  const [tab, setTab] = useState<Tab>("duplicates");
  const current = TABS.find((t) => t.id === tab)!;
  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <PageHeader title="Item master" description="Master-data governance: duplicate item codes and the lifecycle of stocked items, each with the evidence behind it." />
      <Tabs label="Item master views" tabs={TABS} value={tab} onChange={setTab} className="rise" style={enterDelay(1)} />
      <p className="text-sm text-ink-2">{current.blurb}</p>
      {tab === "duplicates" ? <DuplicatesView /> : <LifecycleView />}
    </div>
  );
}
