import type { Municipio, DatabaseStats, UF } from "./types";
import rawMunicipios from "../database/municipios.json";
import rawMunicipiosByUf from "../database/municipios-by-uf.json";
import rawStats from "../database/stats.json";

/** All 5,571 municipalities */
export const municipios: Municipio[] = rawMunicipios as Municipio[];

/** Municipalities grouped by UF */
export const municipiosByUf: Record<UF, Municipio[]> =
  rawMunicipiosByUf as Record<UF, Municipio[]>;

/** Coverage statistics */
export const stats: DatabaseStats = rawStats as DatabaseStats;
