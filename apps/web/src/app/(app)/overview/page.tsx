"use client";

import { Lock } from "lucide-react";
import dynamic from "next/dynamic";

import { AreaBoard } from "@/components/overview/area-board";
import { BelowReorderPanel } from "@/components/overview/below-reorder";
import { InsightsFeed } from "@/components/overview/insights-feed";
import { KpiStrip } from "@/components/overview/kpi-strip";
import { Welcome } from "@/components/overview/welcome";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { useMetricList, usePageMe } from "@/lib/hooks";

/** Panel-shaped placeholder while a chart's code loads (same frame as the panel, so nothing jumps). */
function ChartSlot({ height }: { height: string }) {
  return (
    <div className="panel p-5" aria-hidden>
      <div className="skeleton h-5 w-44 rounded-control" />
      <div className={`skeleton mt-5 w-full rounded-control ${height}`} />
    </div>
  );
}

// The charting library is the largest part of this page's JavaScript: load it beside the data, not before the page.
const ValueBars = dynamic(() => import("@/components/data/value-bars").then((m) => m.ValueBars), {
  ssr: false,
  loading: () => <ChartSlot height="h-48" />,
});
const ValueTrend = dynamic(() => import("@/components/overview/value-trend").then((m) => m.ValueTrend), {
  ssr: false,
  loading: () => <ChartSlot height="h-64" />,
});

export default function OverviewPage() {
  const me = usePageMe();
  const metrics = useMetricList();
  const visible = new Set((metrics.data?.metrics ?? []).map((m) => m.id));
  const canSeeValue = visible.has("inventory_value_total");
  const scope = me?.scope;

  return (
    <div className="@container mx-auto max-w-[96rem] space-y-8">
      <PageHeader
        title="Inventory position"
        actions={
          scope &&
          (scope.all_warehouses
            ? "All warehouses in this tenant"
            : `Limited to ${scope.warehouses.length} warehouse${scope.warehouses.length === 1 ? "" : "s"} by your access scope`)
        }
      />

      <Welcome />

      {metrics.isSuccess && <KpiStrip canSeeValue={canSeeValue} />}

      {metrics.isSuccess && me && <AreaBoard me={me} canSeeValue={canSeeValue} />}

      {metrics.isSuccess && canSeeValue && <ValueTrend />}

      <InsightsFeed />

      {metrics.isSuccess && canSeeValue ? (
        <div className="grid grid-cols-1 gap-4 @5xl:grid-cols-2">
          <ValueBars metricId="inventory_value_by_warehouse" selectKind="warehouse" title="Value by warehouse" labelField="warehouse.name" codeField="warehouse_id" index={0} />
          <ValueBars metricId="inventory_value_by_item_group" selectKind="item_group" title="Value by item group" labelField="item.item_group" humanizeLabels index={1} variant="treemap" />
          <ValueBars metricId="inventory_value_by_abc" selectKind="abc" title="Value by ABC class (as assigned in source)" labelField="item.abc_class" index={2} />
          <ValueBars metricId="inventory_value_by_stage" selectKind="stage" title="Value by inventory stage" labelField="item.inventory_stage" humanizeLabels index={3} />
        </div>
      ) : metrics.isSuccess ? (
        <EmptyState icon={Lock} title="Value breakdowns are hidden because your role does not include cost access." />
      ) : null}

      <div id="below-reorder" className="scroll-mt-20">
        <BelowReorderPanel />
      </div>
    </div>
  );
}
