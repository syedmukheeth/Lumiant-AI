import { clsx } from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "soft";
type Size = "sm" | "md" | "lg";

const BASE =
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-control font-medium whitespace-nowrap transition-[background-color,border-color,color,opacity,transform] active:translate-y-px disabled:pointer-events-none";

// A disabled primary turns neutral (muted plate, muted text, hairline) instead of a washed-out accent, which read as a
// broken grey-blue button. The other variants simply dim.
export const PRIMARY_DISABLED = "disabled:bg-surface-2 disabled:text-ink-3 disabled:ring-1 disabled:ring-line-strong disabled:ring-inset";

const VARIANT: Record<Variant, string> = {
  primary: clsx("bg-accent text-accent-ink hover:bg-accent-strong", PRIMARY_DISABLED),
  secondary: "border border-line-strong bg-surface text-ink shadow-e1 hover:border-control-line hover:bg-surface-2 disabled:opacity-40",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-40",
  soft: "bg-accent-soft text-accent hover:bg-accent hover:text-accent-ink disabled:opacity-40",
};

const SIZE: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs",
  md: "h-9 px-3.5 text-sm",
  lg: "h-10 px-4 text-sm",
};

/** The button recipe as a class string, for links and anchors that must look like a button. */
export function buttonClass({ variant = "secondary", size = "md", className }: { variant?: Variant; size?: Size; className?: string } = {}) {
  return clsx(BASE, VARIANT[variant], SIZE[size], className);
}

type ButtonProps = React.ComponentProps<"button"> & { variant?: Variant; size?: Size };

export function Button({ variant, size, className, type = "button", ...rest }: ButtonProps) {
  return <button type={type} className={buttonClass({ variant, size, className })} {...rest} />;
}

type IconButtonProps = React.ComponentProps<"button"> & { size?: "sm" | "md"; active?: boolean };

/** Square, icon-only button. Give it an `aria-label` (or a visually hidden label inside). */
export function IconButton({ size = "md", active, className, type = "button", ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      className={clsx(
        "relative grid shrink-0 place-items-center rounded-control transition-[background-color,color,transform] active:translate-y-px disabled:pointer-events-none disabled:opacity-40",
        size === "sm" ? "size-6" : "size-8",
        active ? "bg-surface-3 text-ink" : "text-ink-3 hover:bg-surface-2 hover:text-ink",
        className,
      )}
      {...rest}
    />
  );
}
