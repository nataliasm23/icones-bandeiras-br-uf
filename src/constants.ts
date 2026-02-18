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
