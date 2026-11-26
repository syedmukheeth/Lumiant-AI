"use client";

import { Keyboard, Monitor, Moon, PanelLeftClose, PanelLeftOpen, Sun, UserRound } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";

import { Panel } from "@/components/data/widget";
import { isRailCollapsed, toggleRail, useRailCollapsed } from "@/components/shell/rail-state";
import { matchSystemTheme } from "@/components/shell/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { humanize } from "@/lib/format";
import { useMe } from "@/lib/hooks";

type ThemeChoice = "light" | "dark" | "system";
const KEY = "lumiant-theme";
const EVENT = "lumiant:theme";

function readChoice(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

function setChoice(choice: ThemeChoice) {
  if (choice === "system") matchSystemTheme();
  else {
    document.documentElement.dataset.theme = choice;
    try {
      localStorage.setItem(KEY, choice);
    } catch {
      // storage unavailable: applies to this page only
    }
  }
  window.dispatchEvent(new Event(EVENT));
}

const subscribe = (onChange: () => void) => {
  window.addEventListener(EVENT, onChange);
  return () => window.removeEventListener(EVENT, onChange);
};

function Choice({ active, onClick, icon: Icon, label, hint }: { active: boolean; onClick: () => void; icon: typeof Sun; label: string; hint: string }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={
        "flex min-w-0 flex-1 items-start gap-3 rounded-panel border p-4 text-left transition-colors " +
        (active ? "border-accent bg-accent-soft" : "border-line bg-surface hover:border-line-strong")
      }
    >
      <Icon size={18} className={active ? "text-accent" : "text-ink-3"} aria-hidden />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{label}</span>
        <span className="block text-xs text-ink-3">{hint}</span>
      </span>
    </button>
  );
}

const SHORTCUTS: [string, string][] = [
  ["Ctrl K", "Search, jump to a page or ask"],
  ["[", "Collapse or expand the navigation"],
  ["L", "Analyst Lens: pick anything on screen to explain"],
  ["Esc", "Close a sheet, the Lens or the palette"],
];

/** Settings: appearance and navigation are per browser; account details come from the server. */
export function SettingsPage() {
  const me = useMe();
  const theme = useSyncExternalStore(subscribe, readChoice, () => "system" as ThemeChoice);
  const collapsed = useRailCollapsed();
  return (
    <div className="mx-auto max-w-[72rem] space-y-8">
      <PageHeader title="Settings" description="How Lumiant looks and behaves in this browser, and the account you are signed in with." />

      <Panel title="Appearance" subtitle="Saved in this browser. System follows your device's light or dark setting.">
        <div role="radiogroup" aria-label="Theme" className="flex flex-col gap-3 sm:flex-row" data-testid="theme-choice">
          <Choice active={theme === "light"} onClick={() => setChoice("light")} icon={Sun} label="Light" hint="Ivory paper, navy ink" />
          <Choice active={theme === "dark"} onClick={() => setChoice("dark")} icon={Moon} label="Dark" hint="Obsidian, warm ivory" />
          <Choice active={theme === "system"} onClick={() => setChoice("system")} icon={Monitor} label="System" hint="Follow this device" />
        </div>
      </Panel>

      <Panel title="Navigation" subtitle="The side navigation can show labels or only icons.">
        <div role="radiogroup" aria-label="Navigation width" className="flex flex-col gap-3 sm:flex-row">
          <Choice active={!collapsed} onClick={() => isRailCollapsed() && toggleRail()} icon={PanelLeftOpen} label="Expanded" hint="Icons and labels" />
          <Choice active={collapsed} onClick={() => !isRailCollapsed() && toggleRail()} icon={PanelLeftClose} label="Compact" hint="Icons only, more room for data" />
        </div>
      </Panel>

      <Panel title="Account" subtitle="Managed by your organisation; ask an administrator to change roles or warehouses.">
        {me.data ? (
          <dl className="grid gap-4 text-sm sm:grid-cols-2" data-testid="account">
            <div>
              <dt className="eyebrow">Name</dt>
              <dd className="mt-1 flex items-center gap-2 text-ink">
                <UserRound size={14} className="text-ink-3" aria-hidden /> {me.data.user.display_name}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Workspace</dt>
              <dd className="mt-1 text-ink">{me.data.tenant.display_name}</dd>
            </div>
            <div>
              <dt className="eyebrow">Roles</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {me.data.roles.map((r) => (
                  <Badge key={r}>{humanize(r)}</Badge>
                ))}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Warehouses</dt>
              <dd className="mt-1 text-ink">{me.data.scope.all_warehouses ? "All warehouses" : me.data.scope.warehouses.join(", ")}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-ink-3">Loading your account…</p>
        )}
      </Panel>

      <Panel title="Keyboard shortcuts">
        <ul className="divide-y divide-line">
          {SHORTCUTS.map(([keys, what]) => (
            <li key={keys} className="flex items-center justify-between gap-4 py-2.5 text-sm">
              <span className="text-ink-2">{what}</span>
              <kbd className="code rounded-control border border-line bg-surface-2 px-2 py-0.5 text-xs text-ink">{keys}</kbd>
            </li>
          ))}
        </ul>
        <p className="mt-3 flex items-center gap-2 text-xs text-ink-3">
          <Keyboard size={13} aria-hidden /> The design system page shows every colour and chart in the current theme:{" "}
          <Link href="/design" className="text-accent hover:underline">
            open it
          </Link>
          .
        </p>
      </Panel>
    </div>
  );
}
