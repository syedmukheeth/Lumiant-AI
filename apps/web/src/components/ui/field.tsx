import { clsx } from "clsx";
import { ChevronDown, Search } from "lucide-react";

// The shared form-control box: control radius and a boundary that passes 3:1 on every plane. Height is added by each
// control, and width always comes from the parent (controls fill it), so a caller's class never fights a built-in one.
const BOX =
  "w-full min-w-0 rounded-control border border-control-line bg-surface px-2.5 text-sm text-ink transition-[border-color,box-shadow] placeholder:text-ink-3 hover:border-ink-3 disabled:opacity-50";

// Focus is drawn on the box itself (accent border + 1px accent ring = a 2px accent edge), not as a detached outline.
// Controls carry [data-focus-frame] so the global :focus-visible outline does not draw a second box (globals.css).
const FOCUS = "focus:border-accent focus:ring-1 focus:ring-accent";
const FOCUS_WITHIN = "focus-within:border-accent focus-within:ring-1 focus-within:ring-accent";

/**
 * Label above the control, optional hint below. Wraps the control in a <label>, so no id wiring is needed. Give the
 * field a width (`className="w-36"`) to size the control inside it.
 */
export function Field({ label, hint, className, children }: { label: string; hint?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <label className={clsx("flex min-w-0 flex-col gap-1.5", className)}>
      <span className="text-xs font-medium whitespace-nowrap text-ink-2">{label}</span>
      {children}
      {hint && <span className="text-xs text-ink-3">{hint}</span>}
    </label>
  );
}

export function Input({ className, ...rest }: React.ComponentProps<"input">) {
  return <input data-focus-frame className={clsx("h-9", BOX, FOCUS, className)} {...rest} />;
}

export function Textarea({ className, ...rest }: React.ComponentProps<"textarea">) {
  return <textarea data-focus-frame className={clsx(BOX, FOCUS, "py-2 leading-relaxed", className)} {...rest} />;
}

/** Native select (keyboard, mobile pickers and tests keep working) with the shared box and a chevron. */
export function Select({ className, size = "md", children, ...rest }: Omit<React.ComponentProps<"select">, "size"> & { size?: "sm" | "md" }) {
  return (
    <span className={clsx("relative inline-flex min-w-0", className)}>
      <select data-focus-frame className={clsx(size === "sm" ? "h-8" : "h-9", BOX, FOCUS, "appearance-none pr-8")} {...rest}>
        {children}
      </select>
      <ChevronDown size={14} aria-hidden className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-ink-3" />
    </span>
  );
}

/** Text input with a leading search icon; the box shows focus for the input inside it. */
export function SearchInput({ className, inputClassName, ...rest }: React.ComponentProps<"input"> & { inputClassName?: string }) {
  return (
    <span className={clsx("flex h-9 items-center gap-2", BOX, FOCUS_WITHIN, className)}>
      <Search size={14} className="shrink-0 text-ink-3" aria-hidden />
      <input
        data-focus-frame
        className={clsx("h-full w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3", inputClassName)}
        {...rest}
      />
    </span>
  );
}
