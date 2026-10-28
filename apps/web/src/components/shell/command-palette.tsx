"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { CornerDownLeft, LogOut, type LucideIcon, Package, PanelLeft, Search, SunMoon, Sparkles } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Dialog } from "radix-ui";
import { useEffect, useState } from "react";

import type { NavItem } from "@/components/shell/nav";
import { toggleRail } from "@/components/shell/rail-state";
import { toggleTheme } from "@/components/shell/theme-toggle";
import { api, type Envelope, type Row } from "@/lib/api";
import { DUR, EASE, floatIn, REDUCED_DUR } from "@/lib/motion";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nav: readonly NavItem[];
  /** The user may read stock lines (`inventory` section): material search is offered. */
  canSearchMaterials: boolean;
  /** The user may use the assistant: "Ask: …" is offered. */
  canAsk: boolean;
  onNavigate: (href: string) => void;
  onAsk: (question: string) => void;
  onSignOut: () => void;
};

type Material = { id: string; code: string; description: string | null };

/** Distinct materials from stock-line search results (one item can have many lines), in API order. */
export function distinctMaterials(rows: Row[], max = 8): Material[] {
  const seen = new Map<string, Material>();
  for (const r of rows) {
    const id = String(r.item_id ?? "");
    if (!id || seen.has(id)) continue;
    seen.set(id, { id, code: String(r["item.item_code"] ?? id), description: (r["item.description"] as string | null) ?? null });
    if (seen.size >= max) break;
  }
  return [...seen.values()];
}

/**
 * Word-prefix matching ("inv" finds Inventory, "sign" finds Sign out) instead of cmdk's default fuzzy subsequence
 * score, which matches almost any typed question against some page name.
 */
export function paletteFilter(value: string, search: string, keywords: string[] = []): number {
  const query = search.trim().toLowerCase();
  if (!query) return 1;
  const words = [value, ...keywords].join(" ").toLowerCase().split(/[^\p{L}\p{N}]+/u);
  return query.split(/\s+/).every((term) => words.some((w) => w.startsWith(term))) ? 1 : 0;
}

function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

function Keys({ keys }: { keys: string[] }) {
  return (
    <span className="ml-auto flex shrink-0 gap-1" aria-hidden>
      {keys.map((k) => (
        <kbd key={k}>{k}</kbd>
      ))}
    </span>
  );
}

function Item({
  value,
  keywords,
  icon: Icon,
  onSelect,
  children,
  forceMount,
}: {
  value: string;
  keywords?: string[];
  icon: LucideIcon;
  onSelect: () => void;
  children: React.ReactNode;
  forceMount?: boolean;
}) {
  return (
    <Command.Item
      value={value}
      keywords={keywords}
      onSelect={onSelect}
      forceMount={forceMount}
      className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm text-ink-2 transition-colors data-[selected=true]:bg-surface-2 data-[selected=true]:text-ink"
    >
      <Icon size={16} aria-hidden className="shrink-0 text-ink-3" />
      {children}
    </Command.Item>
  );
}

/**
 * ⌘K palette: jump to a page (only the sections the API granted), find a material through the same permission-scoped
 * stock-line search as the inventory explorer, or hand a question to the assistant.
 */
export function CommandPalette({ open, onOpenChange, nav, canSearchMaterials, canAsk, onNavigate, onAsk, onSignOut }: Props) {
  const reduce = useReducedMotion();
  const [search, setSearch] = useState("");
  // Every opening starts empty.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setSearch("");
  }

  const term = useDebounced(search.trim(), 200);
  const lookup = canSearchMaterials && term.length >= 2;
  const found = useQuery({
    queryKey: ["palette-materials", term],
    queryFn: () => api.get<Envelope>("/api/inventory/balances", { q: term, sort: "item_code", dir: "asc", limit: 50 }),
    enabled: open && lookup,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
  const materials = lookup ? distinctMaterials(found.data?.data ?? []) : [];
  const question = search.trim();
  const offersAsk = canAsk && question.length >= 2;

  const run = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay forceMount asChild>
              <motion.div
                className="fixed inset-0 z-(--z-palette) bg-scrim"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduce ? REDUCED_DUR : DUR.fast, ease: EASE.out }}
              />
            </Dialog.Overlay>
            <div className="pointer-events-none fixed inset-x-0 top-[10vh] z-(--z-palette) flex justify-center px-4">
              <Dialog.Content forceMount asChild aria-describedby={undefined}>
                <motion.div
                  {...floatIn(reduce)}
                  className="pointer-events-auto w-full max-w-2xl overflow-hidden rounded-xl border border-glass-line bg-glass-strong shadow-e3 backdrop-blur-xl"
                  data-testid="command-palette"
                >
                  <Dialog.Title className="sr-only">Command palette</Dialog.Title>
                  <Command label="Search pages, materials or ask" loop filter={paletteFilter} className="flex max-h-[min(34rem,72vh)] flex-col">
                    <div className="flex items-center gap-3 border-b border-line px-4 transition-colors focus-within:border-accent/60">
                      <Search size={16} aria-hidden className="shrink-0 text-ink-3" />
                      <Command.Input
                        value={search}
                        onValueChange={setSearch}
                        placeholder={canAsk ? "Jump to a page, find a material, or ask a question…" : "Jump to a page or find a material…"}
                        className="h-13 w-full bg-transparent text-[0.9375rem] text-ink outline-none placeholder:text-ink-3"
                      />
                      <kbd aria-hidden>esc</kbd>
                    </div>
                    <Command.List className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2">
                      {/* cmdk counts only filtered items; material results and "Ask" are always shown, so hide "empty" next to them */}
                      {!offersAsk && materials.length === 0 && (
                        <Command.Empty className="px-3 py-6 text-center text-sm text-ink-3">No matching page or action.</Command.Empty>
                      )}

                      <Command.Group heading="Go to">
                        {nav.map((n) => (
                          <Item key={n.href} value={`Go to ${n.label}`} keywords={[n.group]} icon={n.icon} onSelect={() => run(() => onNavigate(n.href))}>
                            <span className="truncate">{n.label}</span>
                            <Keys keys={["G", n.key.toUpperCase()]} />
                          </Item>
                        ))}
                      </Command.Group>

                      {lookup && (materials.length > 0 || found.isFetching) && (
                        <Command.Group heading="Materials" forceMount>
                          {found.isFetching && materials.length === 0 && (
                            <Command.Loading>
                              <span className="block px-3 py-2 text-sm text-ink-3">Searching stock…</span>
                            </Command.Loading>
                          )}
                          {materials.map((m) => (
                            <Item
                              key={m.id}
                              value={`material ${m.id}`}
                              icon={Package}
                              forceMount
                              onSelect={() => run(() => onNavigate(`/inventory?q=${encodeURIComponent(m.code)}`))}
                            >
                              <span className="figure shrink-0 text-xs text-ink-3">{m.code}</span>
                              <span className="truncate">{m.description ?? "—"}</span>
                              <span className="ml-auto shrink-0 text-xs text-ink-3">View stock</span>
                            </Item>
                          ))}
                        </Command.Group>
                      )}

                      {offersAsk && (
                        <Command.Group heading="Assistant" forceMount>
                          <Item value={`ask ${question}`} icon={Sparkles} forceMount onSelect={() => run(() => onAsk(question))}>
                            <span className="min-w-0 truncate">
                              Ask: <span className="text-ink">“{question}”</span>
                            </span>
                            <CornerDownLeft size={14} aria-hidden className="ml-auto shrink-0 text-ink-3" />
                          </Item>
                        </Command.Group>
                      )}

                      <Command.Group heading="Actions">
                        <Item value="Toggle light or dark theme" keywords={["appearance", "mode"]} icon={SunMoon} onSelect={() => run(toggleTheme)}>
                          Toggle light / dark theme
                        </Item>
                        <Item value="Collapse or expand navigation" keywords={["sidebar", "rail"]} icon={PanelLeft} onSelect={() => run(toggleRail)}>
                          Collapse / expand navigation
                          <Keys keys={["["]} />
                        </Item>
                        <Item value="Sign out" keywords={["logout"]} icon={LogOut} onSelect={() => run(onSignOut)}>
                          Sign out
                        </Item>
                      </Command.Group>
                    </Command.List>
                    <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2 text-[0.6875rem] text-ink-3" aria-hidden>
                      <span className="flex items-center gap-1.5">
                        <kbd>↑</kbd>
                        <kbd>↓</kbd> move <kbd>↵</kbd> open
                      </span>
                      <span className="hidden sm:inline">
                        <kbd>G</kbd> then a key jumps to a page · <kbd>/</kbd> opens this
                      </span>
                    </div>
                  </Command>
                </motion.div>
              </Dialog.Content>
            </div>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
