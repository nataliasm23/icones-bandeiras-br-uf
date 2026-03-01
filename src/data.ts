import type { Municipio, MunicipioIcons, DatabaseStats, UF } from "./types";
import { getDb } from "./db";

interface MunicipioRow {
  ibge_code: number;
  name: string;
  slug: string;
  uf: string;
  uf_name: string;
  region: string;
  region_name: string;
  microrregiao: string | null;
  mesorregiao: string | null;
  regiao_imediata: string | null;
  regiao_intermediaria: string | null;
  populacao_2022: number | null;
  populacao_estimada_2025: number | null;
  area_km2: number | null;
  densidade_demo: number | null;
  latitude: number | null;
  longitude: number | null;
  ddd: string | null;
  cep_sede: string | null;
  has_flag: number;
  has_icons: number;
  flag_source: string | null;
  icons_json: string | null;
}

function rowToMunicipio(row: MunicipioRow): Municipio {
  const m: Municipio = {
    ibge_code: row.ibge_code,
    name: row.name,
    slug: row.slug,
    uf: row.uf as UF,
    uf_name: row.uf_name,
    region: row.region as Municipio["region"],
    region_name: row.region_name,
    has_flag: row.has_flag === 1,
    has_icons: row.has_icons === 1,
    flag_source: row.flag_source ?? null,
  };

  if (row.microrregiao) m.microrregiao = row.microrregiao;
  if (row.mesorregiao) m.mesorregiao = row.mesorregiao;
  if (row.regiao_imediata) m.regiao_imediata = row.regiao_imediata;
  if (row.regiao_intermediaria) m.regiao_intermediaria = row.regiao_intermediaria;
  if (row.populacao_2022 != null) m.populacao_2022 = row.populacao_2022;
  if (row.populacao_estimada_2025 != null) m.populacao_estimada_2025 = row.populacao_estimada_2025;
  if (row.area_km2 != null) m.area_km2 = row.area_km2;
  if (row.densidade_demo != null) m.densidade_demo = row.densidade_demo;
  if (row.latitude != null) m.latitude = row.latitude;
  if (row.longitude != null) m.longitude = row.longitude;
  if (row.ddd) m.ddd = row.ddd;
  if (row.cep_sede) m.cep_sede = row.cep_sede;

  if (row.icons_json) {
    m.icons = JSON.parse(row.icons_json) as MunicipioIcons;
  }

  return m;
}

let _municipios: Municipio[] | null = null;
let _municipiosByUf: Record<UF, Municipio[]> | null = null;
let _stats: DatabaseStats | null = null;

function ensureLoaded(): void {
  if (_municipios) return;

  const db = getDb();
  const rows = db.prepare("SELECT * FROM municipios ORDER BY ibge_code").all() as MunicipioRow[];

  _municipios = rows.map(rowToMunicipio);

  const byUf = {} as Record<UF, Municipio[]>;
  for (const m of _municipios) {
    if (!byUf[m.uf]) byUf[m.uf] = [];
    byUf[m.uf].push(m);
  }
  _municipiosByUf = byUf;

  const metaRow = db.prepare("SELECT value FROM metadata WHERE key = ?").get("stats") as
    | { value: string }
    | undefined;
  _stats = metaRow ? (JSON.parse(metaRow.value) as DatabaseStats) : ({} as DatabaseStats);
}

/** All 5,571 municipalities */
export function getMunicipiosArray(): Municipio[] {
  ensureLoaded();
  return _municipios!;
}

/** Municipalities grouped by UF */
export function getMunicipiosByUfMap(): Record<UF, Municipio[]> {
  ensureLoaded();
  return _municipiosByUf!;
}

/** Coverage statistics */
export function getStats(): DatabaseStats {
  ensureLoaded();
  return _stats!;
}

// Backward-compatible lazy getters
export const municipios: Municipio[] = new Proxy([] as Municipio[], {
  get(_target, prop, receiver) {
    ensureLoaded();
    return Reflect.get(_municipios!, prop, receiver);
  },
});

export const municipiosByUf: Record<UF, Municipio[]> = new Proxy(
  {} as Record<UF, Municipio[]>,
  {
    get(_target, prop, receiver) {
      ensureLoaded();
      return Reflect.get(_municipiosByUf!, prop, receiver);
    },
    ownKeys() {
      ensureLoaded();
      return Reflect.ownKeys(_municipiosByUf!);
    },
    getOwnPropertyDescriptor(_target, prop) {
      ensureLoaded();
      return Object.getOwnPropertyDescriptor(_municipiosByUf!, prop);
    },
  }
);

export const stats: DatabaseStats = new Proxy({} as DatabaseStats, {
  get(_target, prop, receiver) {
    ensureLoaded();
    return Reflect.get(_stats!, prop, receiver);
  },
  ownKeys() {
    ensureLoaded();
    return Reflect.ownKeys(_stats!);
  },
  getOwnPropertyDescriptor(_target, prop) {
    ensureLoaded();
    return Object.getOwnPropertyDescriptor(_stats!, prop);
  },
});
