import * as path from "path";
import type { UF, CepRecord, CepSearchOptions } from "./types";

type BetterSqlite3Database = import("better-sqlite3").Database;

const CEP_COLUMNS = "cep, logradouro, complemento, bairro, localidade, uf, ibge, ddd";

export class CepDatabase {
  private db: BetterSqlite3Database;

  constructor(dbPath?: string) {
    const resolvedPath =
      dbPath ?? path.resolve(__dirname, "..", "..", "database", "municipios-br.sqlite");

    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const Database = require("better-sqlite3") as typeof import("better-sqlite3");
    this.db = new Database(resolvedPath, { readonly: true });
    this.db.pragma("journal_mode = WAL");
  }

  getCep(cep: string): CepRecord | undefined {
    const normalized = cep.replace(/[\s.\-]/g, "");
    return this.db.prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE cep = ?`).get(normalized) as
      | CepRecord
      | undefined;
  }

  getCepsByUf(uf: UF): CepRecord[] {
    return this.db.prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE uf = ?`).all(uf) as CepRecord[];
  }

  getCepsByMunicipio(ibgeCode: string): CepRecord[] {
    return this.db
      .prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE ibge = ?`)
      .all(ibgeCode) as CepRecord[];
  }

  searchCeps(query: string, options?: CepSearchOptions): CepRecord[] {
    const limit = options?.limit ?? 100;

    if (this.hasFts()) {
      return this.searchWithFts(query, options?.uf, limit);
    }

    return this.searchWithLike(query, options?.uf, limit);
  }

  close(): void {
    this.db.close();
  }

  private hasFts(): boolean {
    try {
      const row = this.db
        .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='ceps_fts'")
        .get() as { name: string } | undefined;
      return row !== undefined;
    } catch {
      return false;
    }
  }

  private searchWithFts(query: string, uf: UF | undefined, limit: number): CepRecord[] {
    const ftsQuery = query
      .split(/\s+/)
      .filter(Boolean)
      .map((term) => `"${term}"`)
      .join(" ");

    if (uf) {
      return this.db
        .prepare(
          `SELECT c.cep, c.logradouro, c.complemento, c.bairro, c.localidade, c.uf, c.ibge, c.ddd
           FROM ceps_fts f
           JOIN ceps c ON c.rowid = f.rowid
           WHERE ceps_fts MATCH ? AND c.uf = ?
           LIMIT ?`
        )
        .all(ftsQuery, uf, limit) as CepRecord[];
    }

    return this.db
      .prepare(
        `SELECT c.cep, c.logradouro, c.complemento, c.bairro, c.localidade, c.uf, c.ibge, c.ddd
         FROM ceps_fts f
         JOIN ceps c ON c.rowid = f.rowid
         WHERE ceps_fts MATCH ?
         LIMIT ?`
      )
      .all(ftsQuery, limit) as CepRecord[];
  }

  private searchWithLike(query: string, uf: UF | undefined, limit: number): CepRecord[] {
    const pattern = `%${query}%`;

    if (uf) {
      return this.db
        .prepare(
          `SELECT ${CEP_COLUMNS} FROM ceps
           WHERE uf = ? AND (logradouro LIKE ? OR bairro LIKE ? OR localidade LIKE ?)
           LIMIT ?`
        )
        .all(uf, pattern, pattern, pattern, limit) as CepRecord[];
    }

    return this.db
      .prepare(
        `SELECT ${CEP_COLUMNS} FROM ceps
         WHERE logradouro LIKE ? OR bairro LIKE ? OR localidade LIKE ?
         LIMIT ?`
      )
      .all(pattern, pattern, pattern, limit) as CepRecord[];
  }
}
