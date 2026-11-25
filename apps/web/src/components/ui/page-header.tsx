import { clsx } from "clsx";

/** Page title, one line of explanation, and an optional slot on the right. One per page. */
export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("rise flex flex-wrap items-end justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0">
        <h1 className="font-display text-[1.875rem] leading-tight font-medium tracking-[-0.01em] text-ink">{title}</h1>
        {description && <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-ink-3">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2 text-sm text-ink-3">{actions}</div>}
    </div>
  );
}
