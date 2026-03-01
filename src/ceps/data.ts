import type { UF, CepRecord } from "./types";
import { getDb } from "../db";

const CEP_COLUMNS = "cep, logradouro, complemento, bairro, localidade, uf, ibge, ddd";

export function getRecordsByUf(uf: UF): CepRecord[] {
  const db = getDb();
  return db.prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE uf = ?`).all(uf) as CepRecord[];
}

export function getRecordByCep(cep: string): CepRecord | undefined {
  const db = getDb();
  return db.prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE cep = ?`).get(cep) as
    | CepRecord
    | undefined;
}

/** No-op — kept for backward compatibility */
export function clearCache(): void {
  // SQLite needs no cache management
}
