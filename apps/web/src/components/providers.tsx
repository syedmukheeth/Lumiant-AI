"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig, MotionGlobalConfig } from "motion/react";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import { DUR, EASE } from "@/lib/motion";

/** ISSUES #10, Motion side: animations never start in a hidden tab (no frames there); they jump to their end state. */
function useSkipAnimationsWhileHidden() {
  useEffect(() => {
    const sync = () => {
      MotionGlobalConfig.skipAnimations = document.visibilityState === "hidden";
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Never retry client errors (auth, permission, validation); retry transient server errors once.
            retry: (count, error) => !(error instanceof ApiError && error.status > 0 && error.status < 500) && count < 1,
          },
        },
      }),
  );
  useSkipAnimationsWhileHidden();
  return (
    <QueryClientProvider client={client}>
      {/* reducedMotion="user": with the OS preference set, transform and layout animations are dropped, opacity stays. */}
      <MotionConfig reducedMotion="user" transition={{ duration: DUR.base, ease: EASE.out }}>
        {children}
      </MotionConfig>
    </QueryClientProvider>
  );
}
