import type { ChatResult, DocumentItem, PaginatedLogs, VerifyResult } from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_URL}/documents`);
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function fetchLogs(params: {
  searchText?: string;
  auditUserFilter?: string;
  documentId?: string;
  fromDate?: string;
  toDate?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedLogs> {
  const q = new URLSearchParams();
  if (params.searchText) q.set("text", params.searchText);
  if (params.auditUserFilter) q.set("user_id", params.auditUserFilter);
  if (params.documentId) q.set("document_id", params.documentId);
  if (params.fromDate) q.set("from_date", `${params.fromDate}T00:00:00`);
  if (params.toDate) q.set("to_date", `${params.toDate}T23:59:59`);
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  const res = await fetch(`${API_URL}/audit-logs?${q}`);
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  return res.json();
}

export async function uploadPdf(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/documents/upload`, { method: "POST", body: formData });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail ?? "Upload failed");
  }
  return res.json();
}

export async function sendQuestion(params: {
  query: string;
  userId: string;
  documentId: string | null;
}): Promise<ChatResult> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: params.query,
      user_id: params.userId || "anonymous",
      document_id: params.documentId ? Number(params.documentId) : null,
    }),
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.detail ?? "Chat request failed");
  return payload;
}

export async function verifyLog(id: number): Promise<VerifyResult> {
  const res = await fetch(`${API_URL}/audit-logs/${id}/verify`);
  if (!res.ok) throw new Error("Verification failed");
  return res.json();
}

export function exportLogs(format: "json" | "csv"): void {
  window.open(`${API_URL}/audit-logs/export?format=${format}`, "_blank");
}
