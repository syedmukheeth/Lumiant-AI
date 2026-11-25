"use client";

import { Sparkles } from "lucide-react";

import { Panel } from "@/components/data/widget";
import { Badge, Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Gauge } from "@/components/viz/gauge";
import { HeatCalendar } from "@/components/viz/heat-calendar";
import { KpiCard } from "@/components/viz/kpi-card";
import { ParetoChart } from "@/components/viz/pareto-chart";
import { RadarChart } from "@/components/viz/radar-chart";
import { RiskMatrix } from "@/components/viz/risk-matrix";
import {
  SAMPLE_CALENDAR,
  SAMPLE_PARETO,
  SAMPLE_RADAR,
  SAMPLE_RISK,
  SAMPLE_SPARK,
  SAMPLE_STACK,
  SAMPLE_STACK_SERIES,
  SAMPLE_TIMELINE,
  SAMPLE_TREEMAP,
  SAMPLE_TREND,
  SAMPLE_WATERFALL,
} from "@/components/viz/samples";
import { StackedBars } from "@/components/viz/stacked-bars";
import { Timeline } from "@/components/viz/timeline";
import { Treemap } from "@/components/viz/treemap";
import { TrendArea } from "@/components/viz/trend-area";
import { Waterfall } from "@/components/viz/waterfall";

const SWATCHES: { group: string; tokens: { name: string; note: string }[] }[] = [
  {
    group: "Brand",
    tokens: [
      { name: "--brand-navy", note: "Logo navy" },
      { name: "--brand-teal", note: "Logo teal" },
      { name: "--brand-gold", note: "Logo gold" },
      { name: "--ai", note: "AI signature (gold)" },
    ],
  },
  {
    group: "Planes and ink",
    tokens: [
      { name: "--bg", note: "Page" },
      { name: "--surface", note: "Panel" },
      { name: "--surface-2", note: "Raised" },
      { name: "--surface-3", note: "Floating" },
      { name: "--ink", note: "Primary text" },
      { name: "--ink-2", note: "Secondary text" },
      { name: "--ink-3", note: "Muted text" },
      { name: "--accent", note: "Working accent" },
    ],
  },
  {
    group: "Data: categorical",
    tokens: ["1", "2", "3", "4", "5", "7"].map((n) => ({ name: `--viz-${n}`, note: `Series ${n}` })),
  },
  {
    group: "Data: sequential and diverging",
    tokens: [
      ...["1", "2", "3", "4", "5"].map((n) => ({ name: `--seq-${n}`, note: `Step ${n}` })),
      { name: "--div-neg", note: "Below / over cost" },
      { name: "--div-mid", note: "Neutral" },
      { name: "--div-pos", note: "Above / saving" },
    ],
  },
  {
    group: "Status (always with icon and words)",
    tokens: [
      { name: "--status-good", note: "Good" },
      { name: "--status-warning", note: "Warning" },
      { name: "--status-serious", note: "Serious" },
      { name: "--status-critical", note: "Critical" },
    ],
  },
];

function Swatch({ name, note }: { name: string; note: string }) {
  return (
    <li className="flex items-center gap-3">
      <span className="size-9 shrink-0 rounded-control border border-line shadow-e1" style={{ background: `var(${name})` }} aria-hidden />
      <span className="min-w-0">
        <span className="code block truncate text-xs text-ink">{name}</span>
        <span className="block text-caption text-ink-3">{note}</span>
      </span>
    </li>
  );
}

/** Every token, type size, control and chart of the design system on one page, in the current theme. */
export function DesignShowcase() {
  return (
    <div className="@container mx-auto max-w-[96rem] space-y-6">
      <PageHeader
        title="Design system"
        description="Lumiant's colours, type, controls and charts in the current theme. Switch the theme from the command palette (Ctrl K → Theme) to see the other one."
        actions={<Badge tone="signal">Sample values — not tenant data</Badge>}
      />

      <Panel title="Colour" subtitle="Tokens from app/globals.css. Brand colours come from the official logos.">
        <div className="grid gap-6 @3xl:grid-cols-2 @6xl:grid-cols-3">
          {SWATCHES.map((g) => (
            <section key={g.group}>
              <h3 className="eyebrow mb-3">{g.group}</h3>
              <ul className="grid grid-cols-2 gap-3">
                {g.tokens.map((t) => (
                  <Swatch key={t.name} {...t} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 @5xl:grid-cols-2">
        <Panel title="Type" subtitle="Inter for text and numbers; Geist Mono for identifiers only.">
          <div className="space-y-3">
            <p className="text-hero font-semibold text-ink">Hero 60</p>
            <p className="text-display font-semibold text-ink">Display 44</p>
            <p className="text-page font-semibold text-ink">Page title 26</p>
            <p className="text-section font-semibold text-ink">Section 18</p>
            <p className="text-title font-semibold text-ink">Panel title 15</p>
            <p className="text-sm text-ink-2">Body 14 — the quick review of stock that matters.</p>
            <p className="text-kpi font-semibold text-ink figure">USD 2,767,451.83</p>
            <p className="code text-sm text-ink-2">ITEM-0001042 · LOT 24-118 · 3100</p>
          </div>
        </Panel>
        <Panel title="Controls" subtitle="One primitive layer (components/ui) under every page.">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="primary">Primary</Button>
              <Button>Secondary</Button>
              <Button variant="soft">Soft</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="primary" disabled>
                Disabled
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge>Neutral</Badge>
              <Badge tone="accent">Accent</Badge>
              <Badge tone="signal">Needs attention</Badge>
              <Badge tone="ok">Healthy</Badge>
              <span className="inline-flex items-center gap-1 rounded-full border border-ai-line bg-ai-soft px-2 py-0.5 text-caption font-medium text-ink">
                <Sparkles className="size-3 text-ai" aria-hidden /> AI answer
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Chip>Which items are below reorder level?</Chip>
              <Chip>How is inventory value calculated?</Chip>
            </div>
          </div>
        </Panel>
      </div>

      <section aria-label="KPI cards" className="grid gap-4 @3xl:grid-cols-2 @6xl:grid-cols-4">
        <KpiCard label="Inventory value" value="USD 2.77M" trend={SAMPLE_SPARK} delta={{ direction: "up", text: "1.5%", goodWhen: "down", period: "vs Oct" }} />
        <KpiCard label="Items below reorder" value="18" trend={[24, 22, 25, 21, 19, 20, 18]} tone="critical" delta={{ direction: "down", text: "2", goodWhen: "down", period: "vs last week" }} />
        <KpiCard label="Expiring in 60 days" value="9" unit="lots" trend={[4, 6, 5, 8, 7, 9, 9]} tone="muted" delta={{ direction: "flat", text: "0" }} />
        <KpiCard label="Data quality score" value="92" unit="/ 100" trend={[81, 84, 86, 88, 90, 91, 92]} tone="ai" hint="3 checks need data" />
      </section>

      <div className="grid gap-4 @5xl:grid-cols-2">
        <Panel title="Trend — inventory value" subtitle="TrendArea · area + dashed comparison line">
          <TrendArea rows={SAMPLE_TREND.rows} series={SAMPLE_TREND.series} label="Sample inventory value per month over twelve months, in USD, against a target ceiling." />
        </Panel>
        <Panel title="ABC — value concentration" subtitle="ParetoChart · bars by rank, cumulative share, class bands">
          <ParetoChart items={SAMPLE_PARETO} bands={[80, 95]} label="Sample Pareto curve: thirty items ranked by value with their cumulative share." />
        </Panel>
        <Panel title="Value by item group" subtitle="Treemap · share of the whole">
          <Treemap items={SAMPLE_TREEMAP} label="Sample value by item group as a treemap." />
        </Panel>
        <Panel title="Value by warehouse and stage" subtitle="StackedBars · parts of each whole">
          <StackedBars rows={SAMPLE_STACK} series={SAMPLE_STACK_SERIES} label="Sample value by warehouse split by inventory stage, in USD." />
        </Panel>
        <Panel title="Dormant stock risk" subtitle="RiskMatrix · value at stake × days without movement">
          <RiskMatrix points={SAMPLE_RISK} xLabel="Days without issue" yLabel="Value" xSplit={270} ySplit={100000} label="Sample items plotted by days without movement and value at stake." />
        </Panel>
        <Panel title="Costing methods" subtitle="Waterfall · how one figure becomes another">
          <Waterfall steps={SAMPLE_WATERFALL} label="Sample cost of one item under different costing methods." />
        </Panel>
        <Panel title="Lot expiries by day" subtitle="HeatCalendar · quintile colour steps">
          <HeatCalendar days={SAMPLE_CALENDAR} unitLabel="Lots expiring" label="Sample number of lots expiring per day over six months." />
        </Panel>
        <Panel title="Scores" subtitle="Gauge · RadarChart">
          <div className="grid items-center gap-4 @2xl:grid-cols-[auto_1fr]">
            <Gauge value={92} exact="92" status="Good" label="Data quality score" />
            <RadarChart axes={SAMPLE_RADAR.axes} series={SAMPLE_RADAR.series} label="Sample supplier scorecards across five measures." height={240} />
          </div>
        </Panel>
      </div>

      <Panel title="Commitments timeline" subtitle="Timeline · supply bars against customer due dates (red marks)">
        <Timeline lanes={SAMPLE_TIMELINE.lanes} from={SAMPLE_TIMELINE.from} to={SAMPLE_TIMELINE.to} today={SAMPLE_TIMELINE.today} label="Sample customer orders with their supply plans and due dates." />
      </Panel>
    </div>
  );
}
