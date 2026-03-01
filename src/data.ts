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
  gentilico: string | null;
  bioma: string | null;
  sistema_costeiro: number;
  prefeito: string | null;
  pib: number | null;
  pib_per_capita: number | null;
  taxa_mortalidade_infantil: number | null;
  indice_gini: number | null;
  estabelecimentos_saude: number | null;
  codigo_siafi: string | null;
  fuso_horario: string | null;
  capital: number;
  idhm: number | null;
  veiculos: number | null;
  veiculos_ano: string | null;
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
  if (row.gentilico) m.gentilico = row.gentilico;
  if (row.bioma) m.bioma = row.bioma;
  m.sistema_costeiro = row.sistema_costeiro === 1;
  if (row.prefeito) m.prefeito = row.prefeito;
  if (row.pib != null) m.pib = row.pib;
  if (row.pib_per_capita != null) m.pib_per_capita = row.pib_per_capita;
  if (row.taxa_mortalidade_infantil != null) m.taxa_mortalidade_infantil = row.taxa_mortalidade_infantil;
  if (row.indice_gini != null) m.indice_gini = row.indice_gini;
  if (row.estabelecimentos_saude != null) m.estabelecimentos_saude = row.estabelecimentos_saude;
  if (row.codigo_siafi) m.codigo_siafi = row.codigo_siafi;
  if (row.fuso_horario) m.fuso_horario = row.fuso_horario;
  m.capital = row.capital === 1;
  if (row.idhm != null) m.idhm = row.idhm;
  if (row.veiculos != null) m.veiculos = row.veiculos;
  if (row.veiculos_ano) m.veiculos_ano = row.veiculos_ano;

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
