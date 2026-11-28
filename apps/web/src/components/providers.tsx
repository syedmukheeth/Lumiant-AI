"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import { bindSessionCache } from "@/lib/session-cache";

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
  // After hydration (never during it: the server has no session copy), show the saved session at once (lib/session-cache.ts).
  useEffect(() => bindSessionCache(client), [client]);
  // Motion settings live in the signed-in app (components/shell/motion-provider.tsx), not on public pages.
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
