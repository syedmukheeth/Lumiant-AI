/**
 * Motion system: the single source of truth for timing (docs/02-architecture/FRONTEND.md § Motion).
 *
 * The CSS mirror lives in globals.css (--ease-*, --dur-*, --rise, --z-*); change both together.
 * Values are tuned for a dense working tool, not a marketing page: interactions answer within ~150 ms and nothing
 * travels far. A component that hardcodes a duration or easing has left the system.
 */

/** z-index scale. Never use arbitrary z values in components. */
export const Z = {
  base: 0,
  raised: 10,
  sticky: 20,
  rail: 30,
  nav: 40,
  overlay: 50,
  palette: 60,
} as const;

/**
 * Three curves, three jobs. A fourth needs a reason that can be said out loud.
 * `out` arrive-and-settle (default) · `inOut` symmetric moves (rail width) · `pop` the one accent overshoot.
 */
export const EASE = {
  out: [0.16, 1, 0.3, 1],
  inOut: [0.65, 0, 0.35, 1],
  pop: [0.34, 1.4, 0.64, 1],
} as const;

/** Seconds (Motion's unit). `enter` is for entrance reveals, `fast` for hover/press feedback. */
export const DUR = {
  fast: 0.14,
  base: 0.22,
  slow: 0.36,
  enter: 0.42,
} as const;

/** Reveal cadence in seconds, shared so staggers read as one rhythm. */
export const STAGGER = {
  tight: 0.03,
  base: 0.05,
  loose: 0.08,
} as const;

/** Lift distance (px) of entrance reveals. One value, app-wide. */
export const RISE = 6;

/** Under reduced motion: short enough to read as instant, long enough not to be a hard cut. */
export const REDUCED_DUR = 0.01;

/**
 * The exception to "three curves": shared-layout moves (the active-nav marker) use a critically damped spring so an
 * interrupted move keeps its velocity instead of restarting a curve.
 */
export const LAYOUT_SPRING = { type: "spring", stiffness: 560, damping: 44, mass: 0.7 } as const;

/** Inline style for the n-th item of a CSS `.rise` stagger (capped so long lists never wait). */
export function enterDelay(index: number, step: number = STAGGER.base, max = 8): React.CSSProperties {
  return { animationDelay: `${Math.round(Math.min(index, max) * step * 1000)}ms` };
}

/** Motion props for a floating surface (palette, sheets): fade + small scale; opacity only under reduced motion. */
export function floatIn(reduce: boolean | null) {
  return {
    initial: { opacity: 0, scale: reduce ? 1 : 0.98, y: reduce ? 0 : -RISE },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: reduce ? 1 : 0.98, y: reduce ? 0 : -RISE / 2 },
    transition: { duration: reduce ? REDUCED_DUR : DUR.base, ease: EASE.out },
  } as const;
}
