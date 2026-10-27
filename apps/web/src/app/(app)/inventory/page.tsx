"use client";

import { Suspense } from "react";

import { InventoryExplorer } from "@/components/inventory/explorer";

export default function InventoryPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-3">Loading…</p>}>
      <InventoryExplorer />
    </Suspense>
  );
}
