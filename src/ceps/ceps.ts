import type { UF, CepRecord, CepSearchOptions } from "./types";
import { CEP_UF_PREFIXES } from "../constants";
import { getRecordByCep } from "./data";
import { getDb } from "../db";

const CEP_COLUMNS = "cep, logradouro, complemento, bairro, localidade, uf, ibge, ddd";

export function normalizeCep(cep: string): string {
  return cep.replace(/[\s.\-]/g, "");
}

export function isValidCepFormat(cep: string): boolean {
  return /^\d{8}$/.test(cep) || /^\d{5}-\d{3}$/.test(cep);
}

export function getUfFromCep(cep: string): UF | undefined {
  const normalized = normalizeCep(cep);
  if (!/^\d{8}$/.test(normalized)) return undefined;

  const prefix = parseInt(normalized.substring(0, 5), 10);

  for (const [uf, ranges] of Object.entries(CEP_UF_PREFIXES) as [UF, [number, number][]][]) {
    for (const [start, end] of ranges) {
      if (prefix >= start && prefix <= end) {
        return uf;
      }
    }
  }

  return undefined;
}

export function getCep(cep: string): CepRecord | undefined {
  const normalized = normalizeCep(cep);
  if (!/^\d{8}$/.test(normalized)) return undefined;

  return getRecordByCep(normalized);
}

export function getCepsByUf(uf: UF): CepRecord[] {
  const db = getDb();
  return db.prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE uf = ?`).all(uf) as CepRecord[];
}

export function getCepsByMunicipio(ibgeCode: string): CepRecord[] {
  const db = getDb();
  return db.prepare(`SELECT ${CEP_COLUMNS} FROM ceps WHERE ibge = ?`).all(ibgeCode) as CepRecord[];
}

export function searchCeps(query: string, options?: CepSearchOptions): CepRecord[] {
  const limit = options?.limit ?? 100;
  const db = getDb();
  const pattern = `%${query}%`;

  if (options?.uf) {
    return db
      .prepare(
        `SELECT ${CEP_COLUMNS} FROM ceps
         WHERE uf = ? AND (logradouro LIKE ? OR bairro LIKE ? OR localidade LIKE ?)
         LIMIT ?`
      )
      .all(options.uf, pattern, pattern, pattern, limit) as CepRecord[];
  }

  return db
    .prepare(
      `SELECT ${CEP_COLUMNS} FROM ceps
       WHERE logradouro LIKE ? OR bairro LIKE ? OR localidade LIKE ?
       LIMIT ?`
    )
    .all(pattern, pattern, pattern, limit) as CepRecord[];
}
