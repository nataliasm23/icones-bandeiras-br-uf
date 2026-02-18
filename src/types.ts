/** All 27 Brazilian UF (Unidade Federativa) codes */
export type UF =
  | "AC" | "AL" | "AM" | "AP" | "BA" | "CE" | "DF"
  | "ES" | "GO" | "MA" | "MG" | "MS" | "MT" | "PA"
  | "PB" | "PE" | "PI" | "PR" | "RJ" | "RN" | "RO"
  | "RR" | "RS" | "SC" | "SE" | "SP" | "TO";

/** Brazilian macro-regions */
export type Region = "N" | "NE" | "CO" | "SE" | "S";

/** Icon style variants */
export type FlagStyle = "full" | "rounded" | "circle" | "square-rounded";

/** PNG size variants */
export type PngSize = "png-200" | "png-800";

/** Output format (SVG or one of the PNG sizes) */
export type FlagFormat = "svg" | PngSize;

/** Map of all icon paths for a single municipality */
export interface MunicipioIcons {
  full_svg: string;
  "full_png-200": string;
  "full_png-800": string;
  rounded_svg: string;
  "rounded_png-200": string;
  "rounded_png-800": string;
  circle_svg: string;
  "circle_png-200": string;
  "circle_png-800": string;
  "square-rounded_svg": string;
  "square-rounded_png-200": string;
  "square-rounded_png-800": string;
}

/** A single municipality record from the database */
export interface Municipio {
  ibge_code: number;
  name: string;
  slug: string;
  uf: UF;
  uf_name: string;
  region: Region;
  region_name: string;
  has_flag: boolean;
  has_icons: boolean;
  flag_source: string | null;
  icons?: MunicipioIcons;
}

/** Per-UF coverage statistics */
export interface UFStats {
  total: number;
  with_flag: number;
  with_icons: number;
  coverage_pct: number;
}

/** Per-region coverage statistics */
export interface RegionStats {
  total: number;
  with_flag: number;
  with_icons: number;
  coverage_pct: number;
}

/** Full database statistics */
export interface DatabaseStats {
  total_municipios: number;
  total_with_raw_flag: number;
  total_with_icons: number;
  raw_coverage_pct: number;
  icon_coverage_pct: number;
  total_ufs: number;
  styles: FlagStyle[];
  formats: Record<string, string[]>;
  by_uf: Record<UF, UFStats>;
  by_region: Record<string, RegionStats>;
}
