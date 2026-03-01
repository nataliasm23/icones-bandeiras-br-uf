import * as path from "path";

type BetterSqlite3Database = import("better-sqlite3").Database;

let _db: BetterSqlite3Database | null = null;

const DB_PATH = path.resolve(__dirname, "..", "database", "municipios-br.sqlite");

export function getDb(): BetterSqlite3Database {
  if (!_db) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const Database = require("better-sqlite3") as typeof import("better-sqlite3");
    _db = new Database(DB_PATH, { readonly: true });
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

export function closeDb(): void {
  if (_db) {
    _db.close();
    _db = null;
  }
}
