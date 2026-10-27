"use client";

import { Lock } from "lucide-react";

import { ValueBars } from "@/components/data/value-bars";
import { BelowReorderPanel } from "@/components/overview/below-reorder";
import { KpiStrip } from "@/components/overview/kpi-strip";
import { useMetricList, usePageMe } from "@/lib/hooks";

export default function OverviewPage() {
  const me = usePageMe();
  const metrics = useMetricList();
  const visible = new Set((metrics.data?.metrics ?? []).map((m) => m.id));
  const canSeeValue = visible.has("inventory_value_total");
  const scope = me?.scope;

  return (
    <div className="mx-auto max-w-[96rem] space-y-6">
      <div className="rise flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="eyebrow">Overview</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Inventory position</h1>
        </div>
        {scope && (
          <p className="text-sm text-ink-3">
            {scope.all_warehouses
              ? "All warehouses in this tenant"
              : `Limited to ${scope.warehouses.length} warehouse${scope.warehouses.length === 1 ? "" : "s"} by your access scope`}
          </p>
        )}
      </div>

      {metrics.isSuccess && <KpiStrip canSeeValue={canSeeValue} />}

      {metrics.isSuccess && canSeeValue ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <ValueBars metricId="inventory_value_by_warehouse" title="Value by warehouse" labelField="warehouse.name" codeField="warehouse_id" delay={200} />
          <ValueBars metricId="inventory_value_by_item_group" title="Value by item group" labelField="item.item_group" humanizeLabels delay={240} />
          <ValueBars metricId="inventory_value_by_abc" title="Value by ABC class (as assigned in source)" labelField="item.abc_class" delay={280} />
          <ValueBars metricId="inventory_value_by_stage" title="Value by inventory stage" labelField="item.inventory_stage" humanizeLabels delay={320} />
        </div>
      ) : metrics.isSuccess ? (
        <p className="flex items-center gap-2 rounded-md border border-dashed border-line-strong p-4 text-sm text-ink-3">
          <Lock size={15} aria-hidden /> Value breakdowns are hidden because your role does not include cost access.
        </p>
      ) : null}

      <BelowReorderPanel />
    </div>
  );
}
