import type { UF, Region } from "./types";

/** Full names of all 27 UFs */
export const UF_NAMES: Record<UF, string> = {
  AC: "Acre",
  AL: "Alagoas",
  AM: "Amazonas",
  AP: "Amapá",
  BA: "Bahia",
  CE: "Ceará",
  DF: "Distrito Federal",
  ES: "Espírito Santo",
  GO: "Goiás",
  MA: "Maranhão",
  MG: "Minas Gerais",
  MS: "Mato Grosso do Sul",
  MT: "Mato Grosso",
  PA: "Pará",
  PB: "Paraíba",
  PE: "Pernambuco",
  PI: "Piauí",
  PR: "Paraná",
  RJ: "Rio de Janeiro",
  RN: "Rio Grande do Norte",
  RO: "Rondônia",
  RR: "Roraima",
  RS: "Rio Grande do Sul",
  SC: "Santa Catarina",
  SE: "Sergipe",
  SP: "São Paulo",
  TO: "Tocantins",
};

/** Capital city for each UF */
export const UF_CAPITALS: Record<UF, { name: string; ibgeCode: number }> = {
  AC: { name: "Rio Branco", ibgeCode: 1200401 },
  AL: { name: "Maceió", ibgeCode: 2704302 },
  AM: { name: "Manaus", ibgeCode: 1302603 },
  AP: { name: "Macapá", ibgeCode: 1600303 },
  BA: { name: "Salvador", ibgeCode: 2927408 },
  CE: { name: "Fortaleza", ibgeCode: 2304400 },
  DF: { name: "Brasília", ibgeCode: 5300108 },
  ES: { name: "Vitória", ibgeCode: 3205309 },
  GO: { name: "Goiânia", ibgeCode: 5208707 },
  MA: { name: "São Luís", ibgeCode: 2111300 },
  MG: { name: "Belo Horizonte", ibgeCode: 3106200 },
  MS: { name: "Campo Grande", ibgeCode: 5002704 },
  MT: { name: "Cuiabá", ibgeCode: 5103403 },
  PA: { name: "Belém", ibgeCode: 1501402 },
  PB: { name: "João Pessoa", ibgeCode: 2507507 },
  PE: { name: "Recife", ibgeCode: 2611606 },
  PI: { name: "Teresina", ibgeCode: 2211001 },
  PR: { name: "Curitiba", ibgeCode: 4106902 },
  RJ: { name: "Rio de Janeiro", ibgeCode: 3304557 },
  RN: { name: "Natal", ibgeCode: 2408102 },
  RO: { name: "Porto Velho", ibgeCode: 1100205 },
  RR: { name: "Boa Vista", ibgeCode: 1400100 },
  RS: { name: "Porto Alegre", ibgeCode: 4314902 },
  SC: { name: "Florianópolis", ibgeCode: 4205407 },
  SE: { name: "Aracaju", ibgeCode: 2800308 },
  SP: { name: "São Paulo", ibgeCode: 3550308 },
  TO: { name: "Palmas", ibgeCode: 1721000 },
};

/** UFs grouped by macro-region */
export const REGIONS: Record<Region, UF[]> = {
  N: ["AC", "AM", "AP", "PA", "RO", "RR", "TO"],
  NE: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
  CO: ["DF", "GO", "MS", "MT"],
  SE: ["ES", "MG", "RJ", "SP"],
  S: ["PR", "RS", "SC"],
};

/** Region full names */
export const REGION_NAMES: Record<Region, string> = {
  N: "Norte",
  NE: "Nordeste",
  CO: "Centro-Oeste",
  SE: "Sudeste",
  S: "Sul",
};

/** All 27 UF codes sorted alphabetically */
export const ALL_UFS: UF[] = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF",
  "ES", "GO", "MA", "MG", "MS", "MT", "PA",
  "PB", "PE", "PI", "PR", "RJ", "RN", "RO",
  "RR", "RS", "SC", "SE", "SP", "TO",
];

/**
 * CEP prefix ranges per UF, matching the Correios specification.
 * Each entry maps a UF to an array of [start, end] tuples representing
 * the first 5 digits of the CEP.
 */
export const CEP_UF_PREFIXES: Record<UF, [number, number][]> = {
  AC: [[69900, 69999]],
  AL: [[57000, 57999]],
  AM: [[69000, 69299], [69400, 69899]],
  AP: [[68900, 68999]],
  BA: [[40000, 48999]],
  CE: [[60000, 63999]],
  DF: [[70000, 72799], [73000, 73699]],
  ES: [[29000, 29999]],
  GO: [[72800, 72999], [73700, 76799]],
  MA: [[65000, 65999]],
  MG: [[30000, 39999]],
  MS: [[79000, 79999]],
  MT: [[78000, 78899]],
  PA: [[66000, 68899]],
  PB: [[58000, 58999]],
  PE: [[50000, 56999]],
  PI: [[64000, 64999]],
  PR: [[80000, 87999]],
  RJ: [[20000, 28999]],
  RN: [[59000, 59999]],
  RO: [[76800, 76999]],
  RR: [[69300, 69399]],
  RS: [[90000, 99999]],
  SC: [[88000, 89999]],
  SE: [[49000, 49999]],
  SP: [[1000, 19999]],
  TO: [[77000, 77999]],
};

/**
 * Maps the first 2 digits of an IBGE code to the corresponding UF.
 */
export const IBGE_UF_MAP: Record<string, UF> = {
  "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
  "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
  "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
  "41": "PR", "42": "SC", "43": "RS",
  "50": "MS", "51": "MT", "52": "GO", "53": "DF",
};
