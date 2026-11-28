"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Eye, FileSearch, Lock, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DataBadge } from "@/components/shell/synthetic-tape";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { BrandLogo } from "@/components/ui/brand-logo";
import { api, ApiError, type DevUser, type Me } from "@/lib/api";
import { humanize } from "@/lib/format";
import { useDevUsers } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";
import { queries } from "@/lib/queries";
import { clearSessionCache } from "@/lib/session-cache";
import { KpiCard } from "@/components/viz/kpi-card";
import { SAMPLE_SPARK } from "@/components/viz/samples";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const users = useDevUsers();
  // The Overview opens next: fetch its page shell while the user picks who to sign in as.
  useEffect(() => router.prefetch("/overview"), [router]);
  const login = useMutation({
    mutationFn: (username: string) => api.post<Me>("/api/auth/dev-login", { username }),
    onSuccess: (me) => {
      // Drop anything cached for a previous user before the next page loads.
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "dev-users" });
      clearSessionCache();
      // The sign-in response is the session itself: the shell needs no /api/auth/me round trip, and the Overview's
      // first requests start while the page is still opening.
      queryClient.setQueryData(queries.me().queryKey, me);
      void queryClient.prefetchQuery(queries.meta());
      void queryClient.prefetchQuery(queries.metricList());
      router.replace("/overview");
    },
  });

  const byTenant = new Map<string, DevUser[]>();
  for (const u of users.data?.users ?? []) {
    byTenant.set(u.tenant_name, [...(byTenant.get(u.tenant_name) ?? []), u]);
  }
  const hasExtract = (users.data?.users ?? []).some((u) => u.data_classification === "customer_extract");

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
    <div className="mx-auto flex w-full max-w-2xl min-w-0 flex-col px-4 py-10 sm:py-16">
      <div className="flex items-center justify-between">
        <div className="rise flex flex-col items-start gap-2">
          <h1 className="sr-only">Sign in to Lumiant</h1>
          <BrandLogo height={52} plate />
          <p className="pl-2 text-xs text-ink-3">Inventory intelligence platform</p>
        </div>
        <ThemeToggle />
      </div>

      <div className="rise mt-10 flex items-start gap-3 rounded-panel border border-signal/35 bg-signal-soft p-4" style={enterDelay(1)}>
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-signal" aria-hidden />
        <div>
          <p className="text-sm font-semibold text-ink">Development authentication, not for production</p>
          <p className="mt-1 text-sm leading-relaxed text-ink-2">
            Pick a demo user. Each has a different role and warehouse scope so you can see access control in action.{" "}
            {hasExtract ? (
              <>
                Tenants marked <strong>client extract</strong> hold confidential client data loaded on this machine; all
                others run on <strong>generated</strong> data.
              </>
            ) : (
              <>
                Every tenant below runs on <strong>generated</strong> data.
              </>
            )}
          </p>
        </div>
      </div>

      {users.isPending && <p className="mt-8 text-sm text-ink-3">Loading demo users…</p>}
      {(login.isPending || login.isSuccess) && (
        <p className="mt-8 text-sm text-ink-2" role="status">
          Signing in…
        </p>
      )}
      {users.error instanceof ApiError && users.error.status === 404 && (
        <p className="panel mt-8 p-4 text-sm text-ink-2" role="status">
          Sign-in is handled by your organisation&apos;s identity provider. Open this application through your organisation&apos;s
          gateway or portal.
        </p>
      )}
      {users.error && !(users.error instanceof ApiError && users.error.status === 404) && (
        <p className="mt-8 text-sm text-signal" role="alert">
          {users.error instanceof ApiError ? users.error.message : "Could not load users."} Is the API running on port
          8000?
        </p>
      )}

      <div className={`mt-8 space-y-7 ${login.isPending || login.isSuccess ? "pointer-events-none opacity-50" : ""}`}>
        {[...byTenant.entries()].map(([tenant, list], ti) => (
          <section key={tenant} className="rise" style={enterDelay(2 + ti)}>
            <div className="mb-2.5 flex items-center gap-3">
              <h2 className="text-title font-semibold text-ink">{tenant}</h2>
              <DataBadge
                classification={list[0]?.data_classification}
                synthetic={list[0]?.data_classification !== "customer_extract"}
                compact
              />
            </div>
            <ul className="panel divide-y divide-line overflow-hidden">
              {list.map((u) => (
                <li key={u.username}>
                  <button
                    type="button"
                    onClick={() => login.mutate(u.username)}
                    disabled={login.isPending}
                    className="group flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-2 disabled:opacity-60"
                    data-testid={`login-${u.username}`}
                  >
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-ink">{u.display_name}</span>
                      <span className="mt-0.5 block truncate text-xs text-ink-3">
                        <span className="code">{u.username}</span> · {u.roles.map(humanize).join(", ")}
                      </span>
                    </span>
                    <ArrowRight size={16} className="shrink-0 text-ink-3 transition-[color,transform] group-hover:translate-x-0.5 group-hover:text-accent" />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      {login.error && (
        <p className="mt-4 text-sm text-signal" role="alert">
          {login.error instanceof ApiError ? login.error.message : "Sign-in failed."}
        </p>
      )}
      <p className="mt-10 text-xs text-ink-3">
        New to Lumiant?{" "}
        <Link href="/" className="font-medium text-accent hover:underline">
          See what it does
        </Link>
      </p>
    </div>
    <aside className="hidden border-l border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-dvh lg:flex-col lg:justify-center lg:px-14 xl:px-20" aria-label="About Lumiant">
      <p className="eyebrow text-accent">Inventory intelligence</p>
      <h2 className="font-display mt-3 max-w-md text-[2.5rem] leading-[1.08] font-medium tracking-[-0.015em] text-ink">Every number, with its source.</h2>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-ink-2">
        Dashboards, planning and an analyst that answers in plain language, all on one secured query engine.
      </p>
      <div className="mt-8 grid max-w-md gap-3">
        <KpiCard label="Inventory value (sample)" value="USD 2.77M" trend={SAMPLE_SPARK} delta={{ direction: "up", text: "1.5%", goodWhen: "down", period: "vs Oct" }} />
      </div>
      <ul className="mt-8 max-w-md space-y-2.5 text-sm text-ink-2">
        <li className="flex items-center gap-2.5"><Eye className="size-4 text-accent" aria-hidden /> Read-only connection to your data</li>
        <li className="flex items-center gap-2.5"><FileSearch className="size-4 text-accent" aria-hidden /> Provenance on every figure</li>
        <li className="flex items-center gap-2.5"><Lock className="size-4 text-accent" aria-hidden /> The AI never writes SQL</li>
      </ul>
    </aside>
    </div>
  );
}
