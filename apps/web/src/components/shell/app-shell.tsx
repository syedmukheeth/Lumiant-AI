"use client";

import { useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Clock, Lock, LogOut, PanelLeftClose, PanelLeftOpen, Search, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import Link, { useLinkStatus } from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Tooltip } from "radix-ui";
import { Fragment, useEffect, useState, useSyncExternalStore } from "react";

import { AnalystDock } from "@/components/analyst/analyst-dock";
import { Lens } from "@/components/analyst/lens";
import { bindAnalystUser, resetAnalyst, toggleDock, toggleLens, useAnalyst } from "@/components/analyst/store";
import { CommandPalette } from "@/components/shell/command-palette";
import { type NavItem, navFor, sectionFor } from "@/components/shell/nav";
import { toggleRail, useRailCollapsed } from "@/components/shell/rail-state";
import { DataBadge } from "@/components/shell/synthetic-tape";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Button, IconButton } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { tooltipSurface } from "@/components/ui/float";
import { useShortcuts } from "@/components/shell/use-shortcuts";
import { api, ApiError, type Me } from "@/lib/api";
import { askOnPage, assistantHref } from "@/lib/ask";
import { formatTimestamp, humanize } from "@/lib/format";
import { useMe, useTenantMeta } from "@/lib/hooks";
import { LAYOUT_SPRING } from "@/lib/motion";

function scopeLabel(me: Me) {
  if (me.scope.all_warehouses) return "All warehouses";
  if (me.scope.departments.length) return `${me.scope.departments.join(", ")} · ${me.scope.warehouses.length} wh`;
  return me.scope.warehouses.join(", ");
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

const noSubscribe = () => () => {};

/** Apple keyboards show ⌘ for the palette shortcut; known only after hydration (server renders "Ctrl"). */
const useIsApple = () =>
  useSyncExternalStore(noSubscribe, () => /Mac|iPhone|iPad/.test(navigator.userAgent), () => false);

/** Pulses while the link's navigation is in flight (only inside a <Link>). */
function PendingDot() {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden
      className={clsx(
        "absolute top-1/2 right-2 size-1.5 -translate-y-1/2 rounded-full bg-accent transition-opacity",
        // animate-pulse animates opacity itself, so it may only run while pending
        pending ? "opacity-100 motion-safe:animate-pulse" : "opacity-0",
      )}
    />
  );
}

function RailLink({ item, active, collapsed }: { item: NavItem; active: boolean; collapsed: boolean }) {
  const Icon = item.icon;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <Link
          href={item.href}
          aria-current={active ? "page" : undefined}
          aria-keyshortcuts={`G ${item.key.toUpperCase()}`}
          className={clsx(
            "relative flex shrink-0 flex-col items-center gap-1 rounded-control px-3 py-1.5 text-caption font-medium transition-colors md:flex-row md:gap-3 md:py-2 md:text-sm",
            "md:rail-collapsed:justify-center md:rail-collapsed:px-0",
            active ? "text-ink" : "text-ink-2 hover:bg-surface-2/70 hover:text-ink",
          )}
        >
          {active && (
            <motion.span
              layoutId="rail-active"
              transition={LAYOUT_SPRING}
              aria-hidden
              className="absolute inset-0 rounded-control bg-surface-2 before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-accent max-md:before:hidden"
            />
          )}
          <Icon size={18} aria-hidden className={clsx("relative shrink-0", active ? "text-accent" : "text-ink-3")} />
          <span className="relative whitespace-nowrap md:rail-collapsed:sr-only">{item.label}</span>
          <PendingDot />
        </Link>
      </Tooltip.Trigger>
      {collapsed && (
        <Tooltip.Portal>
          <Tooltip.Content
            side="right"
            sideOffset={10}
            className={`z-(--z-overlay) hidden md:flex md:items-center md:gap-2 ${tooltipSurface}`}
          >
            {item.label}
            <span className="flex gap-0.5">
              <kbd>G</kbd>
              <kbd>{item.key.toUpperCase()}</kbd>
            </span>
          </Tooltip.Content>
        </Tooltip.Portal>
      )}
    </Tooltip.Root>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const me = useMe();
  const meta = useTenantMeta(me.isSuccess);
  const collapsed = useRailCollapsed();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const apple = useIsApple();

  const signOut = async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      resetAnalyst();
      queryClient.clear();
      router.replace("/login");
    }
  };

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) {
      // Expired or invalid session: clear the cookie so the router stops treating us as signed in.
      api.post("/api/auth/logout").finally(() => {
        resetAnalyst();
        queryClient.clear();
        router.replace("/login");
      });
    }
  }, [me.error, queryClient, router]);

  useEffect(() => {
    if (me.data) bindAnalystUser(`${me.data.tenant.id}:${me.data.user.id}`);
  }, [me.data]);

  const user = me.data;
  const nav = user ? navFor(user.sections) : [];
  // A page whose section the role lacks (reached by typing its URL) is not mounted at all, so it fires no requests.
  // The API enforces the same rule server-side; this keeps the UI from even asking. Until the session loads, a
  // section page waits rather than requesting data it may not be allowed to see.
  const route = sectionFor(pathname);
  const pageAllowed = !route || (user ? user.sections.includes(route.section) : undefined);
  const unreachable = me.error && !(me.error instanceof ApiError && me.error.status === 401);
  const canAsk = !!user?.sections.includes("assistant");
  const canCost = !!user?.permissions.includes("cost:read");
  const analyst = useAnalyst();

  const ask = (question: string) => {
    // Already on the assistant: hand the question over without remounting (keeps the conversation).
    if (pathname.startsWith("/assistant")) askOnPage(question);
    else router.push(assistantHref(question));
  };

  useShortcuts({
    nav,
    onPalette: () => setPaletteOpen((o) => !o),
    onNavigate: (href) => router.push(href),
    onToggleRail: toggleRail,
    onDock: canAsk ? toggleDock : undefined,
    onLens: canAsk ? toggleLens : undefined,
  });

  return (
    <Tooltip.Provider delayDuration={250} skipDelayDuration={100}>
      <div className="min-h-dvh md:grid md:grid-cols-[var(--rail-w)_minmax(0,1fr)]">
        <aside
          className={clsx(
            "fixed inset-x-0 bottom-0 z-(--z-nav) border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]",
            "md:sticky md:top-0 md:bottom-auto md:flex md:h-dvh md:flex-col md:border-t-0 md:border-r md:pb-0",
          )}
        >
          <div className="hidden h-14 items-center gap-2.5 px-4 md:flex md:rail-collapsed:justify-center md:rail-collapsed:px-0">
            <Link href="/overview" aria-label="Lumiant home" className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="grid size-7 shrink-0 place-items-center rounded-control bg-accent text-dense font-bold text-accent-ink"
              >
                L
              </span>
              <span className="leading-none md:rail-collapsed:sr-only">
                <span className="block text-sm font-semibold tracking-[0.14em] text-ink">LUMIANT</span>
                <span className="mt-1 block text-caption leading-none text-ink-3">Inventory intelligence</span>
              </span>
            </Link>
          </div>

          <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 py-1.5 md:flex-1 md:flex-col md:gap-0.5 md:overflow-x-visible md:overflow-y-auto md:py-3">
            {user
              ? nav.map((item, i) => (
                  <Fragment key={item.href}>
                    {item.group !== nav[i - 1]?.group && (
                      <p
                        aria-hidden
                        className={clsx("hidden px-3 pb-1.5 text-caption font-medium text-ink-3 md:block md:rail-collapsed:hidden", i > 0 && "mt-5")}
                      >
                        {item.group}
                      </p>
                    )}
                    {item.group !== nav[i - 1]?.group && i > 0 && (
                      <span aria-hidden className="mx-3 my-2 hidden border-t border-line md:rail-collapsed:block" />
                    )}
                    <RailLink item={item} active={pathname.startsWith(item.href)} collapsed={collapsed} />
                  </Fragment>
                ))
              : [0, 1, 2, 3].map((i) => <span key={i} aria-hidden className="skeleton mx-1 h-8 w-16 shrink-0 rounded-control md:w-auto" />)}
          </nav>

          <div className="mt-auto hidden border-t border-line p-3 md:block" data-testid="user-card">
            {user ? (
              <div className="flex items-center gap-3 md:rail-collapsed:justify-center">
                <span
                  aria-hidden
                  title={user.user.display_name}
                  className="grid size-8 shrink-0 place-items-center rounded-full border border-line-strong bg-surface-2 text-caption font-semibold text-ink-2"
                >
                  {initials(user.user.display_name)}
                </span>
                <div className="min-w-0 md:rail-collapsed:sr-only">
                  <p className="truncate text-dense font-medium text-ink">{user.user.display_name}</p>
                  <p className="truncate text-xs text-ink-3">{user.roles.map(humanize).join(", ")}</p>
                  <p className="truncate text-caption text-ink-3">Scope: {scopeLabel(user)}</p>
                </div>
              </div>
            ) : (
              <p className="text-xs text-ink-3" role="status">
                Checking your session…
              </p>
            )}
            <div className="mt-3 flex items-center justify-between gap-2 md:rail-collapsed:flex-col">
              <Button variant="ghost" size="sm" onClick={signOut}>
                <LogOut size={14} aria-hidden /> <span className="md:rail-collapsed:sr-only">Sign out</span>
              </Button>
              <IconButton
                onClick={toggleRail}
                aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
                aria-keyshortcuts="["
                title={collapsed ? "Expand navigation  [" : "Collapse navigation  ["}
              >
                {collapsed ? <PanelLeftOpen size={16} aria-hidden /> : <PanelLeftClose size={16} aria-hidden />}
              </IconButton>
            </div>
          </div>
        </aside>

        <div className="min-w-0">
          <header className="glass sticky top-0 z-(--z-sticky) border-b border-line">
            <div className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2 sm:px-6 xl:flex-nowrap">
              <div className="flex min-w-0 shrink items-center gap-3">
                <Link href="/overview" aria-label="Lumiant home" className="md:hidden">
                  <span aria-hidden className="grid size-7 place-items-center rounded-control bg-accent text-dense font-bold text-accent-ink">
                    L
                  </span>
                </Link>
                <span className="min-w-0 truncate text-sm font-semibold text-ink">{user?.tenant.display_name ?? " "}</span>
                {meta.data && (
                  <span className="shrink-0">
                    <DataBadge classification={meta.data.data_classification} synthetic={meta.data.synthetic} />
                  </span>
                )}
              </div>

              <button
                type="button"
                onClick={() => setPaletteOpen(true)}
                aria-keyshortcuts="Control+K Meta+K"
                aria-haspopup="dialog"
                className="order-last flex h-9 w-full items-center gap-2.5 rounded-control border border-line-strong bg-surface px-3 text-left text-sm text-ink-3 transition-colors hover:border-control-line hover:text-ink-2 xl:order-none xl:w-auto xl:max-w-md xl:min-w-48 xl:flex-1"
              >
                <Search size={15} aria-hidden className="shrink-0" />
                <span className="truncate">{canAsk ? "Search, jump or ask…" : "Search or jump…"}</span>
                <span className="ml-auto hidden items-center gap-0.5 sm:flex" aria-hidden>
                  <kbd>{apple ? "⌘" : "Ctrl"}</kbd>
                  <kbd>K</kbd>
                </span>
              </button>

              <div className="flex shrink-0 items-center gap-3 text-xs text-ink-3">
                <span className={clsx("flex items-center gap-1.5 whitespace-nowrap", meta.data?.stale && "text-signal")} data-testid="data-as-of">
                  <Clock size={14} aria-hidden />
                  Data as of <span className="figure text-ink-2">{formatTimestamp(meta.data?.data_as_of)}</span>
                  {meta.data?.stale && " · stale"}
                </span>
                {canAsk && (
                  <button
                    type="button"
                    onClick={toggleDock}
                    aria-pressed={analyst.open}
                    aria-keyshortcuts="Control+J Meta+J"
                    title={`Analyst (${apple ? "⌘" : "Ctrl"}+J) · Lens (L)`}
                    data-testid="analyst-toggle"
                    className={clsx(
                      "inline-flex h-8 items-center gap-1.5 rounded-control border px-2.5 text-xs font-medium transition-[background-color,border-color,color,transform] active:translate-y-px",
                      analyst.open
                        ? "border-accent/50 bg-accent-soft text-accent"
                        : "border-line-strong bg-surface text-ink-2 hover:border-control-line hover:text-ink",
                    )}
                  >
                    <Sparkles size={14} aria-hidden /> <span className="hidden sm:inline">Analyst</span>
                  </button>
                )}
                <ThemeToggle />
                <IconButton onClick={signOut} className="md:hidden" aria-label="Sign out">
                  <LogOut size={16} />
                </IconButton>
              </div>
            </div>
          </header>
          <main className="app-main px-4 pt-6 pb-28 transition-[padding] duration-(--dur-slow) sm:px-6 md:pb-10 lg:px-8">
            {unreachable && (
              <p role="alert" className="mb-4 rounded-control border border-signal/40 bg-signal-soft p-3 text-sm text-ink">
                The service could not be reached. {me.error instanceof ApiError ? me.error.message : ""}
              </p>
            )}
            {/* Route transition: a short fade on every page change (opacity only, so reduced motion keeps it). */}
            <div key={pathname} className="route-enter">
              {pageAllowed === true ? (
                children
              ) : pageAllowed === false ? (
                <div className="mx-auto max-w-[96rem]" data-testid="page-forbidden">
                  <EmptyState
                    icon={Lock}
                    title="Not available for your role."
                    hint="Your organisation has not given your role access to this page. Pick another page from the menu."
                  />
                </div>
              ) : null}
            </div>
          </main>
        </div>
      </div>

      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        nav={nav}
        canSearchMaterials={!!user?.sections.includes("inventory")}
        canAsk={canAsk}
        onNavigate={(href) => router.push(href)}
        onAsk={ask}
        onSignOut={signOut}
      />
      {canAsk && (
        <>
          <AnalystDock canCost={canCost} />
          <Lens />
        </>
      )}
    </Tooltip.Provider>
  );
}
