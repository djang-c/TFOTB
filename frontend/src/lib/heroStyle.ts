/**
 * How the home-page artwork sits on the page.
 *   "flow"    fills the hero, fades into the page on every side and runs on past the hero as you scroll
 *   "classic" the earlier look: the picture centred at its own shape inside the hero, with a hard edge
 * To go back, set VITE_HERO_STYLE=classic when building, or change DEFAULT below.
 */
export type HeroStyle = "flow" | "classic";
const DEFAULT: HeroStyle = "flow";
export const HERO_STYLE: HeroStyle =
  import.meta.env["VITE_HERO_STYLE"] === "classic" ? "classic" : DEFAULT;

/** Fades the artwork out at the top and bottom so no straight edge shows. */
export const HERO_FADE =
  "linear-gradient(to bottom, transparent 0%, #000 14%, #000 58%, transparent 100%)";
