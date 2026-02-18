import type { Municipio, UF } from "./types";
import { municipios, municipiosByUf } from "./data";

/** Lazily-built index: ibge_code → Municipio */
let _index: Map<number, Municipio> | null = null;

function getIndex(): Map<number, Municipio> {
  if (!_index) {
    _index = new Map();
    for (const m of municipios) {
      _index.set(m.ibge_code, m);
    }
  }
  return _index;
}

/**
 * Look up a municipality by its 7-digit IBGE code.
 *
 * @example
 * ```ts
 * const sp = getMunicipio(3550308);
 * console.log(sp?.name); // "São Paulo"
 * ```
 */
export function getMunicipio(ibgeCode: number): Municipio | undefined {
  return getIndex().get(ibgeCode);
}

/**
 * Get all municipalities for a given UF.
 *
 * @example
 * ```ts
 * const rj = getMunicipiosByUf("RJ");
 * console.log(rj.length); // 92
 * ```
 */
export function getMunicipiosByUf(uf: UF): Municipio[] {
  return municipiosByUf[uf] ?? [];
}

/**
 * Get municipalities that have generated flag icons.
 * Optionally filter by UF.
 *
 * @example
 * ```ts
 * const allWithFlags = getMunicipiosWithFlags();
 * const spWithFlags = getMunicipiosWithFlags("SP");
 * ```
 */
export function getMunicipiosWithFlags(uf?: UF): Municipio[] {
  const source = uf ? getMunicipiosByUf(uf) : municipios;
  return source.filter((m) => m.has_icons);
}

/**
 * Search municipalities by name or slug (case-insensitive substring match).
 *
 * @example
 * ```ts
 * const results = searchMunicipios("paulo");
 * // [{ name: "São Paulo", ... }, { name: "São Paulo do Potengi", ... }, ...]
 * ```
 */
export function searchMunicipios(query: string): Municipio[] {
  const q = query.toLowerCase().trim();
  if (!q) return [];
  return municipios.filter(
    (m) => m.name.toLowerCase().includes(q) || m.slug.includes(q)
  );
}
