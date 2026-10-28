import { Boxes, Coins, Compass, FileText, LayoutDashboard, type LucideIcon, MessageSquareText, ShieldAlert, ShieldCheck } from "lucide-react";

import type { Me } from "@/lib/api";

export type NavItem = {
  section: Me["sections"][number];
  href: string;
  label: string;
  icon: LucideIcon;
  /** Second key of the "G then key" shortcut. */
  key: string;
  group: "Monitor" | "Analyze" | "Govern";
};

/** Every page of the app. The API decides which sections a user gets (`Me.sections`); the UI only hides the rest. */
export const NAV: readonly NavItem[] = [
  { section: "overview", href: "/overview", label: "Overview", icon: LayoutDashboard, key: "o", group: "Monitor" },
  { section: "overview", href: "/explore", label: "Explore", icon: Compass, key: "e", group: "Monitor" },
  { section: "inventory", href: "/inventory", label: "Inventory", icon: Boxes, key: "i", group: "Analyze" },
  { section: "risks", href: "/risks", label: "Risks", icon: ShieldAlert, key: "r", group: "Analyze" },
  { section: "costs", href: "/costs", label: "Costs", icon: Coins, key: "c", group: "Analyze" },
  { section: "assistant", href: "/assistant", label: "Assistant", icon: MessageSquareText, key: "a", group: "Analyze" },
  { section: "reports", href: "/reports", label: "Reports", icon: FileText, key: "p", group: "Govern" },
  { section: "admin", href: "/admin", label: "Admin", icon: ShieldCheck, key: "d", group: "Govern" },
];

export const navFor = (sections: readonly string[]) => NAV.filter((n) => sections.includes(n.section));
