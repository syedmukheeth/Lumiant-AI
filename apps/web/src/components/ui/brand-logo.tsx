import Image from "next/image";
import { clsx } from "clsx";

/**
 * The official Lumiant logo (docs/BRAND_IMPLEMENTATION.md). Both supplied images are rendered and CSS shows the one
 * for the active theme (`:root` = dark, `[data-theme="light"]` = light — set before first paint by
 * public/theme-init.js), so there is no flash and no hydration mismatch.
 *
 * The artwork is never redrawn, recoloured or re-encoded by Next (`unoptimized`) and always keeps its aspect ratio
 * (one dimension set, the other auto). The dark file is the exact supplied image. The light file is the supplied
 * image without its top two pixel rows — a thin teal decorative line the owner asked to remove; every other pixel is
 * identical (the untouched originals are kept in docs/brand/). Each image carries its own background (dark: navy
 * #101a2e, light: white) and sits on a `--surface` plate set to those same colours, so no box shows.
 */
const DARK = { src: "/brand/lumiant-logo-dark.png", width: 232, height: 75 };
const LIGHT = { src: "/brand/lumiant-logo-light.png", width: 230, height: 78 };
const ALT = "Lumiant — Together we grow";

type Props = {
  /** Display height in px (width follows the aspect ratio). Ignored when `width` is set. */
  height?: number;
  /** Display width in px (height follows). The supplied files are ~230 px wide: stay at or below that. */
  width?: number;
  plate?: boolean;
  className?: string;
};

export function BrandLogo({ height = 32, width, plate = false, className }: Props) {
  const style = width ? ({ width, height: "auto" } as const) : ({ height, width: "auto" } as const);
  return (
    <span className={clsx("inline-flex shrink-0 items-center", plate && "rounded-control bg-surface px-2 py-1", className)}>
      <Image src={DARK.src} width={DARK.width} height={DARK.height} alt={ALT} unoptimized priority className="block max-w-full light:hidden" style={style} data-testid="brand-logo-dark" />
      <Image src={LIGHT.src} width={LIGHT.width} height={LIGHT.height} alt={ALT} unoptimized priority className="hidden max-w-full light:block" style={style} data-testid="brand-logo-light" />
    </span>
  );
}
