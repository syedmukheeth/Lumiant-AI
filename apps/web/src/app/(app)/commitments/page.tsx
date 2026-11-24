"use client";

import { Suspense } from "react";

import { Skeleton } from "@/components/data/widget";
import { CommitmentsPage } from "@/components/planning/commitments-page";

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <CommitmentsPage />
    </Suspense>
  );
}
