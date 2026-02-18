// Types
export type {
  UF,
  Region,
  FlagStyle,
  PngSize,
  FlagFormat,
  Municipio,
  MunicipioIcons,
  UFStats,
  RegionStats,
  DatabaseStats,
} from "./types";

// Constants
export {
  UF_NAMES,
  UF_CAPITALS,
  REGIONS,
  REGION_NAMES,
  ALL_UFS,
} from "./constants";

// Data
export { municipios, municipiosByUf, stats } from "./data";

// Municipio lookups
export {
  getMunicipio,
  getMunicipiosByUf,
  getMunicipiosWithFlags,
  searchMunicipios,
} from "./municipios";

// Flag path resolution
export {
  getFlagPath,
  getFlagUrl,
  getAllFlagPaths,
  buildFlagPath,
} from "./flags";
