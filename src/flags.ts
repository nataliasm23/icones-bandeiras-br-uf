import type { FlagStyle, FlagFormat, MunicipioIcons } from "./types";
import { getMunicipio } from "./municipios";

/** Style suffix used in file names */
const STYLE_SUFFIX: Record<FlagStyle, string> = {
  full: "full",
  rounded: "rounded",
  circle: "circle",
  "square-rounded": "sq",
};

/**
 * Build the icon-map key for a given style + format.
 * Example: ("circle", "svg") → "circle_svg"
 *          ("full", "png-200") → "full_png-200"
 */
function iconKey(style: FlagStyle, format: FlagFormat): keyof MunicipioIcons {
  return `${style}_${format}` as keyof MunicipioIcons;
}

/**
 * Get the relative file path for a municipality flag icon.
 * Paths are relative to the package `dist/` directory.
 *
 * @returns Relative path (e.g. `"circle/svg/SP/3550308-sao-paulo-circle.svg"`) or `null` if not found.
 *
 * @example
 * ```ts
 * const path = getFlagPath(3550308, "circle", "svg");
 * // "circle/svg/SP/3550308-sao-paulo-circle.svg"
 * ```
 */
export function getFlagPath(
  ibgeCode: number,
  style: FlagStyle,
  format: FlagFormat
): string | null {
  const m = getMunicipio(ibgeCode);
  if (!m?.icons) return null;

  const key = iconKey(style, format);
  return m.icons[key] ?? null;
}

/**
 * Get a full URL for a municipality flag icon, given a base URL
 * where the `dist/` directory is served.
 *
 * @param baseUrl - URL prefix (e.g. `"https://cdn.example.com/flags"`)
 * @returns Full URL or `null` if no icon exists.
 *
 * @example
 * ```ts
 * const url = getFlagUrl(3550308, "circle", "png-200", "https://cdn.example.com/flags");
 * // "https://cdn.example.com/flags/circle/png-200/SP/3550308-sao-paulo-circle.png"
 * ```
 */
export function getFlagUrl(
  ibgeCode: number,
  style: FlagStyle,
  format: FlagFormat,
  baseUrl: string
): string | null {
  const path = getFlagPath(ibgeCode, style, format);
  if (!path) return null;
  const base = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  return `${base}/${path}`;
}

/**
 * Get all icon paths for a municipality.
 *
 * @returns The full `MunicipioIcons` map or `null` if the municipality has no icons.
 *
 * @example
 * ```ts
 * const icons = getAllFlagPaths(3550308);
 * console.log(icons?.circle_svg);
 * // "circle/svg/SP/3550308-sao-paulo-circle.svg"
 * ```
 */
export function getAllFlagPaths(ibgeCode: number): MunicipioIcons | null {
  const m = getMunicipio(ibgeCode);
  return m?.icons ?? null;
}

/**
 * Build a flag file path from components (without database lookup).
 * Useful when you know the UF and slug already.
 *
 * @example
 * ```ts
 * const path = buildFlagPath("SP", 3550308, "sao-paulo", "circle", "svg");
 * // "circle/svg/SP/3550308-sao-paulo-circle.svg"
 * ```
 */
export function buildFlagPath(
  uf: string,
  ibgeCode: number,
  slug: string,
  style: FlagStyle,
  format: FlagFormat
): string {
  const suffix = STYLE_SUFFIX[style];
  const ext = format === "svg" ? "svg" : "png";
  return `${style}/${format}/${uf}/${ibgeCode}-${slug}-${suffix}.${ext}`;
}
