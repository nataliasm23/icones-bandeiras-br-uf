// Types
export type {
  UF,
  CepRecord,
  CepSearchOptions,
  CepStats,
  CepSyncOptions,
  CepSyncProgress,
  CepSyncResult,
} from "./types";

// Main API
export {
  getCep,
  getCepsByUf,
  getCepsByMunicipio,
  searchCeps,
  getUfFromCep,
  isValidCepFormat,
  normalizeCep,
} from "./ceps";

// Sync
export { syncCeps, getCepsSyncDate } from "./sync";

// Cache management
export { clearCache } from "./data";

// SQLite adapter
export { CepDatabase } from "./sqlite";
