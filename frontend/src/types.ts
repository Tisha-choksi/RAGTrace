export type DocumentItem = {
  id: number;
  filename: string;
  chunk_count: number;
  uploaded_at: string;
};

export type RetrievedChunk = {
  text: string;
  document_id: number;
  filename: string;
  page: number;
  chunk_index: number;
  score?: number;
};

export type ChatResult = {
  query: string;
  response: string;
  model: string;
  timestamp: string;
  sha256_hash: string;
  retrieved_chunks: RetrievedChunk[];
  audit_log_id: number;
  alerts: string[];
  pii_masked: boolean;
  groundedness_score?: number | null;
};

export type AuditLog = {
  id: number;
  user_id: string;
  query: string;
  retrieved_chunks: RetrievedChunk[];
  response: string;
  model: string;
  sha256_hash: string;
  alerts: string[];
  pii_masked: boolean;
  groundedness_score?: number | null;
  timestamp: string;
  document_id?: number;
  document_name?: string;
};

export type VerifyResult = {
  id: number;
  stored_hash: string;
  recomputed_hash: string;
  verified: boolean;
};

export type PaginatedLogs = {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
};

export type LogFilters = {
  searchText: string;
  auditUserFilter: string;
  fromDate: string;
  toDate: string;
  offset: number;
};
