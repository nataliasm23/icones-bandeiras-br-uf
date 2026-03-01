import type { UF } from "../types";

export type { UF };

export interface CepRecord {
  cep: string;
  logradouro: string;
  complemento: string;
  bairro: string;
  localidade: string;
  uf: UF;
  ibge: string;
  ddd: string;
}

export interface CepSearchOptions {
  uf?: UF;
  limit?: number;
}

export interface CepStats {
  total_ceps: number;
  by_uf: Record<string, { count: number; file_size_kb: number }>;
  generated_at: string;
  sources: Record<string, number>;
}

export interface CepSyncOptions {
  /** Re-sync CEPs whose synced_at is older than N days. Default: only synced_at IS NULL */
  staleDays?: number;
  /** Filter by UF(s) */
  ufs?: UF[];
  /** Max CEPs to process per run (0 = unlimited) */
  batchLimit?: number;
  /** AbortSignal for cancellation */
  signal?: AbortSignal;
  /** Progress callback */
  onProgress?: (progress: CepSyncProgress) => void;
  /** Delay between requests in ms (default: 350) */
  delayMs?: number;
  /** Per-request timeout in ms (default: 10000) */
  timeoutMs?: number;
}

export interface CepSyncProgress {
  processed: number;
  total: number;
  current: string;
  synced: number;
  notFound: number;
  errors: number;
}

export interface CepSyncResult {
  processed: number;
  synced: number;
  notFound: number;
  errors: number;
  cancelled: boolean;
  durationSeconds: number;
}
