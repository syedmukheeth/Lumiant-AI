# Brand Implementation

## Status (23 Nov 2026): DONE — official logos integrated and verified

| File | Source | Size | SHA-256 (first 16) | Used in |
|---|---|---|---|---|
| `apps/web/public/brand/lumiant-logo-dark.png` | supplied attachment 1 (dark mode) | 232×75, navy `#101a2e` background | `095F0B2476D9C3E8` | dark theme |
| `apps/web/public/brand/lumiant-logo-light.png` | supplied attachment 2 (light mode), top 2 pixel rows removed | 230×78, white background | `3BFD546EB2C03586` | light theme |

The dark file is **byte-identical** to its attachment. The light file is the attachment with only its top two pixel rows removed (see below); rows 2–79 are pixel-identical to the original (0 differing pixels). Neither is redrawn or recoloured: `next/image` runs with `unoptimized`, the height is set and the width is auto, so the aspect ratio is preserved (verified: 161×52 rendered for 232×75).

- **Component:** `apps/web/src/components/ui/brand-logo.tsx` renders both images, and CSS (`light:` variant on `[data-theme="light"]`, set before first paint) shows exactly one. There is no flash and no hydration mismatch.
- **Placements:** sign-in page (52 px, on a plate), sidebar (34 px, and 17 px when the rail is collapsed), mobile header (26 px, on a plate). Report exports and the favicon still use the previous assets (no square mark was supplied).
- **Background match:** the logo always sits on a `--logo-plate` set to its own file's background (dark: navy `#101a2e`, light: white), so the image edge disappears into a deliberate tile on any plane. Since DEC-031 the dark planes are warm charcoal, no longer navy.
- **Palette from the artwork:** navy `#101a2e`, navy `#112545` (wordmark), gold `#c4872f` (tagline), teal `#045b62`. Gold is used only for non-text marks: the active-page indicator and the "recommended supplier" mark. In light theme gold reaches 4.4:1, below AA for small text.
- **Middleware:** `brand/` is excluded from the sign-in redirect so the logo loads on the sign-in page (`src/proxy.ts`).
- **Tests:** e2e `planning.spec.ts` checks that the right file shows per theme, the natural sizes (232 wide; 230×78), and that the sidebar logo renders at least 150 px wide.
- **Future:** request an official SVG or transparent master and a square mark for the favicon. The supplied PNGs are small (about 230 px wide) and are displayed only at or below their native size to avoid pixelation.

## Earlier status (kept for history)

On 23 Nov the files were first missing from the project, and integration was correctly stopped until the owner supplied them.

## 23 Nov 2026 — logo size and the teal line

- **Sidebar logo enlarged** as requested: 160 px wide on desktop (rendered 160×52 dark, 160×54 light; aspect ratio preserved), tagline legible. The header grew to 80 px. Collapsed rail: 17 px tall mark; mobile header: 26 px on a surface plate.
- **Thin teal line removed.** It was part of the supplied light-mode image itself: pixel rows 0–1 were a full-width teal band (`#045b62`, `#3d8086`), not CSS. Only those two rows were cropped. Nothing else changed: same colours, same proportions, no redraw.
- **Originals kept unchanged** in `docs/brand/lumiant-logo-light.original.png` and `docs/brand/lumiant-logo-dark.original.png` (`FF3A949250DDEAC8`, `095F0B2476D9C3E8`).
- Verified in the browser in both themes; the dark logo is never shown on a light background.
