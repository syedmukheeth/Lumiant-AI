"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";

import { DataBadge } from "@/components/shell/synthetic-tape";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { BrandLogo } from "@/components/ui/brand-logo";
import { api, ApiError, type DevUser } from "@/lib/api";
import { humanize } from "@/lib/format";
import { useDevUsers } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const users = useDevUsers();
  const login = useMutation({
    mutationFn: (username: string) => api.post("/api/auth/dev-login", { username }),
    onSuccess: () => {
      // Drop anything cached for a previous user before the next page loads.
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "dev-users" });
      router.replace("/overview");
    },
  });

  const byTenant = new Map<string, DevUser[]>();
  for (const u of users.data?.users ?? []) {
    byTenant.set(u.tenant_name, [...(byTenant.get(u.tenant_name) ?? []), u]);
  }
  const hasExtract = (users.data?.users ?? []).some((u) => u.data_classification === "customer_extract");

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 py-10 sm:py-16">
      <div className="flex items-center justify-between">
        <div className="rise flex flex-col items-start gap-2">
          <h1 className="sr-only">Lumiant — sign in</h1>
          <BrandLogo height={52} plate />
          <p className="pl-2 text-xs text-ink-3">Inventory intelligence platform</p>
        </div>
        <ThemeToggle />
      </div>

      <div className="rise mt-10 flex items-start gap-3 rounded-panel border border-signal/35 bg-signal-soft p-4" style={enterDelay(1)}>
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-signal" aria-hidden />
        <div>
          <p className="text-sm font-semibold text-ink">Development authentication — not for production</p>
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
    </div>
  );
}
