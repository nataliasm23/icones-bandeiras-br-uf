import * as path from "path";
import type { UF, CepSyncOptions, CepSyncProgress, CepSyncResult } from "./types";
import { getDb } from "../db";

type BetterSqlite3Database = import("better-sqlite3").Database;

const DB_PATH = path.resolve(__dirname, "..", "..", "database", "municipios-br.sqlite");

let _syncRunning = false;

// ---------------------------------------------------------------------------
// Schema migration (idempotent)
// ---------------------------------------------------------------------------

function ensureSyncedAtColumn(db: BetterSqlite3Database): void {
  const cols = db.pragma("table_info(ceps)") as { name: string }[];
  if (cols.some((c) => c.name === "synced_at")) return;

  db.exec("ALTER TABLE ceps ADD COLUMN synced_at TEXT");
  db.exec("CREATE INDEX IF NOT EXISTS idx_ceps_synced_at ON ceps(synced_at)");
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

interface ApiCepResult {
  logradouro?: string;
  complemento?: string;
  bairro?: string;
  localidade?: string;
  uf?: string;
  ibge?: string;
  ddd?: string;
  notFound?: boolean;
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(
  url: string,
  timeoutMs: number,
  retries = 3
): Promise<Response | null> {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
      if (resp.status === 429 && attempt < retries - 1) {
        await delay(1000 * 2 ** attempt);
        continue;
      }
      return resp;
    } catch {
      if (attempt < retries - 1) {
        await delay(1000 * 2 ** attempt);
      }
    }
  }
  return null;
}

async function fetchCepFromApi(
  cep: string,
  timeoutMs: number
): Promise<ApiCepResult | null> {
  // Primary: BrasilAPI
  const brasilResp = await fetchWithRetry(
    `https://brasilapi.com.br/api/cep/v2/${cep}`,
    timeoutMs
  );
  if (brasilResp && brasilResp.ok) {
    const data = (await brasilResp.json()) as Record<string, unknown>;
    if (data.cep) {
      return {
        logradouro: (data.street as string) || undefined,
        complemento: undefined, // BrasilAPI doesn't return complemento
        bairro: (data.neighborhood as string) || undefined,
        localidade: (data.city as string) || undefined,
        uf: (data.state as string) || undefined,
      };
    }
  }
  if (brasilResp && brasilResp.status === 404) {
    return { notFound: true };
  }

  // Fallback: ViaCEP
  const viaCepResp = await fetchWithRetry(
    `https://viacep.com.br/ws/${cep}/json/`,
    timeoutMs
  );
  if (viaCepResp && viaCepResp.ok) {
    const data = (await viaCepResp.json()) as Record<string, unknown>;
    if (data.erro) {
      return { notFound: true };
    }
    return {
      logradouro: (data.logradouro as string) || undefined,
      complemento: (data.complemento as string) || undefined,
      bairro: (data.bairro as string) || undefined,
      localidade: (data.localidade as string) || undefined,
      uf: (data.uf as string) || undefined,
      ibge: (data.ibge as string) || undefined,
      ddd: (data.ddd as string) || undefined,
    };
  }

  return null; // both failed
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns the ISO 8601 timestamp of the last completed sync run, or null.
 */
export function getCepsSyncDate(): string | null {
  const db = getDb();
  const row = db
    .prepare("SELECT value FROM metadata WHERE key = 'ceps_last_sync'")
    .get() as { value: string } | undefined;
  return row?.value ?? null;
}

/**
 * Syncs CEP records from BrasilAPI / ViaCEP in the background.
 * Non-blocking — each iteration yields to the event loop via async fetch + delay.
 * WAL mode allows concurrent readonly readers.
 */
export async function syncCeps(options?: CepSyncOptions): Promise<CepSyncResult> {
  if (_syncRunning) {
    throw new Error("A CEP sync is already running");
  }

  _syncRunning = true;
  const start = Date.now();
  const delayMs = options?.delayMs ?? 350;
  const timeoutMs = options?.timeoutMs ?? 10_000;
  const batchLimit = options?.batchLimit ?? 0;
  const signal = options?.signal;
  const onProgress = options?.onProgress;

  const result: CepSyncResult = {
    processed: 0,
    synced: 0,
    notFound: 0,
    errors: 0,
    cancelled: false,
    durationSeconds: 0,
  };

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const Database = require("better-sqlite3") as typeof import("better-sqlite3");
  const writeDb: BetterSqlite3Database = new Database(DB_PATH, { readonly: false });

  try {
    writeDb.pragma("journal_mode = WAL");
    writeDb.pragma("busy_timeout = 5000");

    ensureSyncedAtColumn(writeDb);

    // Build WHERE clause
    const conditions: string[] = [];
    const params: unknown[] = [];

    if (options?.staleDays != null) {
      conditions.push(
        "(synced_at IS NULL OR synced_at < datetime('now', '-' || ? || ' days'))"
      );
      params.push(options.staleDays);
    } else {
      conditions.push("synced_at IS NULL");
    }

    if (options?.ufs && options.ufs.length > 0) {
      const placeholders = options.ufs.map(() => "?").join(", ");
      conditions.push(`uf IN (${placeholders})`);
      params.push(...options.ufs);
    }

    let query = `SELECT cep, ibge, ddd FROM ceps WHERE ${conditions.join(" AND ")}`;
    if (batchLimit > 0) {
      query += ` LIMIT ?`;
      params.push(batchLimit);
    }

    const pending = writeDb.prepare(query).all(...params) as {
      cep: string;
      ibge: string;
      ddd: string;
    }[];

    const total = pending.length;

    const updateStmt = writeDb.prepare(`
      UPDATE ceps
      SET logradouro = ?, complemento = ?, bairro = ?,
          localidade = ?, uf = ?, ibge = ?, ddd = ?,
          source = 'correios', synced_at = ?
      WHERE cep = ?
    `);

    const markSyncedStmt = writeDb.prepare(`
      UPDATE ceps SET synced_at = ? WHERE cep = ?
    `);

    const COMMIT_EVERY = 500;
    let txOpen = false;

    for (let i = 0; i < total; i++) {
      if (signal?.aborted) {
        result.cancelled = true;
        break;
      }

      const row = pending[i];

      if (!txOpen) {
        writeDb.exec("BEGIN");
        txOpen = true;
      }

      try {
        const apiResult = await fetchCepFromApi(row.cep, timeoutMs);

        if (apiResult === null) {
          // Both APIs failed
          result.errors++;
        } else if (apiResult.notFound) {
          // CEP not found — mark synced_at so we don't retry immediately
          const now = new Date().toISOString();
          markSyncedStmt.run(now, row.cep);
          result.notFound++;
        } else {
          const now = new Date().toISOString();
          updateStmt.run(
            apiResult.logradouro ?? "",
            apiResult.complemento ?? "",
            apiResult.bairro ?? "",
            apiResult.localidade ?? "",
            apiResult.uf ?? "",
            // Preserve ibge/ddd from DB if API didn't return them
            apiResult.ibge ?? row.ibge,
            apiResult.ddd ?? row.ddd,
            now,
            row.cep
          );
          result.synced++;
        }
      } catch {
        result.errors++;
      }

      result.processed++;

      if (onProgress) {
        onProgress({
          processed: result.processed,
          total,
          current: row.cep,
          synced: result.synced,
          notFound: result.notFound,
          errors: result.errors,
        });
      }

      // Commit every N rows
      if (txOpen && (result.processed % COMMIT_EVERY === 0 || i === total - 1)) {
        writeDb.exec("COMMIT");
        txOpen = false;
      }

      // Rate limit — also yields to the event loop
      if (i < total - 1) {
        await delay(delayMs);
      }
    }

    // Commit any remaining transaction
    if (txOpen) {
      writeDb.exec("COMMIT");
    }

    // Rebuild FTS for synced rows
    if (result.synced > 0) {
      writeDb.exec("DELETE FROM ceps_fts");
      writeDb.exec(
        "INSERT INTO ceps_fts(rowid, cep, logradouro, bairro, localidade) " +
          "SELECT rowid, cep, logradouro, bairro, localidade FROM ceps"
      );
    }

    // Update global sync date
    if (result.processed > 0) {
      const now = new Date().toISOString();
      writeDb
        .prepare("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)")
        .run("ceps_last_sync", now);
    }
  } finally {
    writeDb.close();
    _syncRunning = false;
    result.durationSeconds = Math.round((Date.now() - start) / 1000 * 100) / 100;
  }

  return result;
}
