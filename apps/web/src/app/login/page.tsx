"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";

import { SyntheticTape } from "@/components/shell/synthetic-tape";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { api, ApiError, type DevUser } from "@/lib/api";
import { humanize } from "@/lib/format";
import { useDevUsers } from "@/lib/hooks";

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

  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4 py-10 sm:py-16">
      <div className="flex items-start justify-between">
        <div className="rise">
          <p className="text-2xl font-extrabold tracking-[0.22em] text-ink sm:text-3xl">LUMIANT</p>
          <p className="eyebrow mt-1">Inventory intelligence platform</p>
        </div>
        <ThemeToggle />
      </div>

      <div className="rise mt-10 rounded-md border border-signal/40 bg-signal-soft p-4" style={{ animationDelay: "60ms" }}>
        <p className="flex items-center gap-2 text-sm font-semibold text-ink">
          <ShieldAlert size={16} className="text-signal" aria-hidden />
          Development authentication — not for production
        </p>
        <p className="mt-1 text-sm text-ink-2">
          Pick a demo user. Each has a different role and warehouse scope so you can see access control in action. Every
          tenant below runs on <strong>generated</strong> data.
        </p>
      </div>

      {users.isPending && <p className="mt-8 text-sm text-ink-3">Loading demo users…</p>}
      {(login.isPending || login.isSuccess) && (
        <p className="mt-8 text-sm text-ink-2" role="status">
          Signing in…
        </p>
      )}
      {users.error && (
        <p className="mt-8 text-sm text-signal" role="alert">
          {users.error instanceof ApiError ? users.error.message : "Could not load users."} Is the API running on port
          8000?
        </p>
      )}

      <div className={`mt-8 space-y-8 ${login.isPending || login.isSuccess ? "pointer-events-none opacity-50" : ""}`}>
        {[...byTenant.entries()].map(([tenant, list], ti) => (
          <section key={tenant} className="rise" style={{ animationDelay: `${120 + ti * 80}ms` }}>
            <div className="mb-3 flex items-center gap-3">
              <h2 className="text-sm font-semibold text-ink">{tenant}</h2>
              <SyntheticTape compact />
            </div>
            <ul className="divide-y divide-line overflow-hidden rounded-md border border-line bg-surface">
              {list.map((u) => (
                <li key={u.username}>
                  <button
                    type="button"
                    onClick={() => login.mutate(u.username)}
                    disabled={login.isPending}
                    className="group flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-2 disabled:opacity-60"
                    data-testid={`login-${u.username}`}
                  >
                    <span>
                      <span className="block text-sm font-medium text-ink">{u.display_name}</span>
                      <span className="figure block text-xs text-ink-3">
                        {u.username} · {u.roles.map(humanize).join(", ")}
                      </span>
                    </span>
                    <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5 group-hover:text-ink" />
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
