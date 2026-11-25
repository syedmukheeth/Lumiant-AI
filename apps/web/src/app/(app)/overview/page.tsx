"use client";

import { Lock } from "lucide-react";

import { ValueBars } from "@/components/data/value-bars";
import { AreaBoard } from "@/components/overview/area-board";
import { BelowReorderPanel } from "@/components/overview/below-reorder";
import { InsightsFeed } from "@/components/overview/insights-feed";
import { KpiStrip } from "@/components/overview/kpi-strip";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { useMetricList, usePageMe } from "@/lib/hooks";

export default function OverviewPage() {
  const me = usePageMe();
  const metrics = useMetricList();
  const visible = new Set((metrics.data?.metrics ?? []).map((m) => m.id));
  const canSeeValue = visible.has("inventory_value_total");
  const scope = me?.scope;

  return (
    <div className="@container mx-auto max-w-[96rem] space-y-6">
      <PageHeader
        title="Inventory position"
        actions={
          scope &&
          (scope.all_warehouses
            ? "All warehouses in this tenant"
            : `Limited to ${scope.warehouses.length} warehouse${scope.warehouses.length === 1 ? "" : "s"} by your access scope`)
        }
      />

      {metrics.isSuccess && <KpiStrip canSeeValue={canSeeValue} />}

      {metrics.isSuccess && me && <AreaBoard me={me} canSeeValue={canSeeValue} />}

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
