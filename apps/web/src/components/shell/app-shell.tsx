"use client";

import { useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Boxes, Clock, Coins, Compass, FileText, LayoutDashboard, LogOut, MessageSquareText, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { SyntheticTape } from "@/components/shell/synthetic-tape";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { api, ApiError, type Me } from "@/lib/api";
import { formatTimestamp, humanize } from "@/lib/format";
import { useMe, useTenantMeta } from "@/lib/hooks";

const NAV = [
  { section: "overview", href: "/overview", label: "Overview", icon: LayoutDashboard },
  { section: "overview", href: "/explore", label: "Explore", icon: Compass },
  { section: "inventory", href: "/inventory", label: "Inventory", icon: Boxes },
  { section: "risks", href: "/risks", label: "Risks", icon: ShieldAlert },
  { section: "costs", href: "/costs", label: "Costs", icon: Coins },
  { section: "assistant", href: "/assistant", label: "Assistant", icon: MessageSquareText },
  { section: "reports", href: "/reports", label: "Reports", icon: FileText },
] as const;

function scopeLabel(me: Me) {
  if (me.scope.all_warehouses) return "All warehouses";
  if (me.scope.departments.length) return `${me.scope.departments.join(", ")} · ${me.scope.warehouses.length} wh`;
  return me.scope.warehouses.join(", ");
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const me = useMe();
  const meta = useTenantMeta(me.isSuccess);

  const signOut = async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      queryClient.clear();
      router.replace("/login");
    }
  };

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) {
      // Expired or invalid session: clear the cookie so the router stops treating us as signed in.
      api.post("/api/auth/logout").finally(() => {
        queryClient.clear();
        router.replace("/login");
      });
    }
  }, [me.error, queryClient, router]);

  // The page always renders (its own queries handle loading/permissions); only the chrome waits for the session.
  const user = me.data;
  const nav = user ? NAV.filter((n) => user.sections.includes(n.section)) : [];
  const unreachable = me.error && !(me.error instanceof ApiError && me.error.status === 401);

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="flex flex-col border-b border-line bg-surface md:sticky md:top-0 md:h-dvh md:border-r md:border-b-0">
        <div className="flex items-center justify-between gap-2 px-4 py-4 md:block">
          <Link href="/overview" className="block">
            <span className="text-[1.05rem] font-extrabold tracking-[0.2em] text-ink">LUMIANT</span>
            <span className="eyebrow mt-0.5 block !text-[0.625rem]">Inventory intelligence</span>
          </Link>
          <div className="md:hidden">
            <ThemeToggle />
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:pb-0">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex items-center gap-2.5 rounded-sm px-3 py-2 text-sm transition-colors",
                  active ? "bg-ink text-surface" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                )}
              >
                <Icon size={16} aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto hidden border-t border-line p-4 md:block" data-testid="user-card">
          {user ? (
            <>
              <p className="text-sm font-semibold text-ink">{user.user.display_name}</p>
              <p className="mt-0.5 text-xs text-ink-3">{user.roles.map(humanize).join(", ")}</p>
              <p className="figure mt-1 text-[0.6875rem] text-ink-3">Scope: {scopeLabel(user)}</p>
            </>
          ) : (
            <p className="text-xs text-ink-3" role="status">
              Checking your session…
            </p>
          )}
          <button
            type="button"
            onClick={signOut}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-ink-2 hover:text-signal"
          >
            <LogOut size={13} aria-hidden /> Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 border-b border-line bg-bg/90 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2.5 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <span className="truncate text-sm font-semibold text-ink">{user?.tenant.display_name ?? " "}</span>
              {meta.data?.synthetic && <SyntheticTape />}
            </div>
            <div className="flex items-center gap-3 text-xs text-ink-3">
              <span className={clsx("flex items-center gap-1.5", meta.data?.stale && "text-signal")} data-testid="data-as-of">
                <Clock size={13} aria-hidden />
                Data as of <span className="figure text-ink-2">{formatTimestamp(meta.data?.data_as_of)}</span>
                {meta.data?.stale && " · stale"}
              </span>
              <span className="hidden md:inline">
                <ThemeToggle />
              </span>
              <button type="button" onClick={signOut} className="md:hidden" aria-label="Sign out">
                <LogOut size={15} />
              </button>
            </div>
          </div>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8">
          {unreachable && (
            <p role="alert" className="mb-4 rounded-md border border-signal/40 bg-signal-soft p-3 text-sm text-ink">
              The service could not be reached. {me.error instanceof ApiError ? me.error.message : ""}
            </p>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
