import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { navFor } from "@/components/shell/nav";
import { toggleRail } from "@/components/shell/rail-state";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { useShortcuts } from "@/components/shell/use-shortcuts";

const root = document.documentElement;

afterEach(() => {
  delete root.dataset.theme;
  delete root.dataset.rail;
  delete root.dataset.motion;
  localStorage.clear();
});

describe("useShortcuts", () => {
  function setup() {
    const handlers = { nav: navFor(["overview", "inventory"]), onPalette: vi.fn(), onNavigate: vi.fn(), onToggleRail: vi.fn() };
    renderHook(() => useShortcuts(handlers));
    return handlers;
  }
  const press = (key: string, init: KeyboardEventInit = {}, target: EventTarget = window) =>
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }));

  it("opens the palette with Ctrl+K, ⌘K and /", () => {
    const h = setup();
    press("k", { ctrlKey: true });
    press("K", { metaKey: true });
    press("/");
    expect(h.onPalette).toHaveBeenCalledTimes(3);
  });

  it("jumps to a granted page with G then a key, and ignores keys of pages not granted", () => {
    const h = setup();
    press("g");
    press("i");
    expect(h.onNavigate).toHaveBeenCalledWith("/inventory");
    press("g");
    press("d"); // admin: not granted
    expect(h.onNavigate).toHaveBeenCalledTimes(1);
  });

  it("never fires single-key shortcuts while typing", () => {
    const h = setup();
    const input = document.createElement("input");
    document.body.append(input);
    press("g", {}, input);
    press("i", {}, input);
    press("[", {}, input);
    press("/", {}, input);
    expect(h.onNavigate).not.toHaveBeenCalled();
    expect(h.onToggleRail).not.toHaveBeenCalled();
    expect(h.onPalette).not.toHaveBeenCalled();
    press("k", { ctrlKey: true }, input); // the palette shortcut works everywhere
    expect(h.onPalette).toHaveBeenCalledTimes(1);
    input.remove();
  });

  it("toggles the rail with [", () => {
    const h = setup();
    press("[");
    expect(h.onToggleRail).toHaveBeenCalledTimes(1);
  });
});

describe("theme and rail state", () => {
  it("dark is the default; the toggle switches to light and back and remembers it", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Toggle light or dark theme" });
    fireEvent.click(button);
    expect(root.dataset.theme).toBe("light");
    expect(localStorage.getItem("lumiant-theme")).toBe("light");
    fireEvent.click(button);
    expect(root.dataset.theme).toBe("dark");
    expect(localStorage.getItem("lumiant-theme")).toBe("dark");
  });

  it("the rail collapses and expands through <html data-rail> and is remembered", () => {
    toggleRail();
    expect(root.dataset.rail).toBe("collapsed");
    expect(localStorage.getItem("lumiant-rail")).toBe("collapsed");
    toggleRail();
    expect(root.dataset.rail).toBeUndefined();
    expect(localStorage.getItem("lumiant-rail")).toBe("expanded");
  });
});

describe("public/theme-init.js", () => {
  const source = readFileSync(resolve(process.cwd(), "public", "theme-init.js"), "utf8");
  let visibility: DocumentVisibilityState = "visible";
  type FakeAnimation = { finish: () => void; playState: string; effect: { getComputedTiming: () => { endTime: number } } };
  let animations: FakeAnimation[] = [];
  const fake = (endTime: number): FakeAnimation => ({ finish: vi.fn(), playState: "running", effect: { getComputedTiming: () => ({ endTime }) } });

  // Each boot adds a visibilitychange listener; remove them so tests stay independent.
  const added: [string, EventListenerOrEventListenerObject][] = [];
  const addListener = document.addEventListener.bind(document);
  beforeEach(() => {
    vi.spyOn(document, "addEventListener").mockImplementation((type: string, listener: EventListenerOrEventListenerObject) => {
      added.push([type, listener]);
      addListener(type, listener);
    });
    visibility = "visible";
    animations = [];
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
    Object.defineProperty(document, "getAnimations", { configurable: true, value: () => animations });
  });

  afterEach(() => {
    for (const [type, listener] of added.splice(0)) document.removeEventListener(type, listener);
    vi.restoreAllMocks();
  });

  const boot = () => new Function(source)();
  const setVisibility = (v: DocumentVisibilityState) => {
    visibility = v;
    document.dispatchEvent(new Event("visibilitychange"));
  };

  it("applies the saved theme and rail before paint", () => {
    localStorage.setItem("lumiant-theme", "light");
    localStorage.setItem("lumiant-rail", "collapsed");
    boot();
    expect(root.dataset.theme).toBe("light");
    expect(root.dataset.rail).toBe("collapsed");
  });

  it("ignores unknown saved values", () => {
    localStorage.setItem("lumiant-theme", "neon");
    boot();
    expect(root.dataset.theme).toBeUndefined();
  });

  it("ISSUES #10: a page loaded in a hidden tab gets no entrance animations", () => {
    visibility = "hidden";
    boot();
    expect(root.dataset.motion).toBe("off");
  });

  it("ISSUES #10: hiding the tab finishes finite animations (never infinite ones); returning finishes the re-applied ones", () => {
    boot();
    expect(root.dataset.motion).toBeUndefined();
    const entrance = fake(420);
    const shimmer = fake(Infinity);
    animations = [entrance, shimmer];
    setVisibility("hidden");
    expect(root.dataset.motion).toBe("off");
    expect(entrance.finish).toHaveBeenCalledTimes(1);
    expect(shimmer.finish).not.toHaveBeenCalled();

    const reapplied = fake(420);
    animations = [reapplied, shimmer];
    setVisibility("visible");
    expect(root.dataset.motion).toBeUndefined();
    expect(reapplied.finish).toHaveBeenCalledTimes(1);
    expect(shimmer.finish).not.toHaveBeenCalled();
  });
});
