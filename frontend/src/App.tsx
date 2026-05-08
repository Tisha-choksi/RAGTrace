import React, { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  History,
  Search,
  Send,
  ShieldCheck,
  Upload
} from "lucide-react";
import { createRoot } from "react-dom/client";
import "./main.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type DocumentItem = {
  id: number;
  filename: string;
  chunk_count: number;
  uploaded_at: string;
};

type RetrievedChunk = {
  text: string;
  document_id: number;
  filename: string;
  page: number;
  chunk_index: number;
  score?: number;
};

type ChatResult = {
  query: string;
  response: string;
  model: string;
  timestamp: string;
  sha256_hash: string;
  retrieved_chunks: RetrievedChunk[];
  audit_log_id: number;
  alerts: string[];
  pii_masked: boolean;
};

type AuditLog = {
  id: number;
  user_id: string;
  query: string;
  retrieved_chunks: RetrievedChunk[];
  response: string;
  model: string;
  sha256_hash: string;
  alerts: string[];
  pii_masked: boolean;
  timestamp: string;
  document_id?: number;
  document_name?: string;
};

type VerifyResult = {
  id: number;
  stored_hash: string;
  recomputed_hash: string;
  verified: boolean;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function App() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [userId, setUserId] = useState("demo-user");
  const [documentId, setDocumentId] = useState("");
  const [query, setQuery] = useState("");
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [searchText, setSearchText] = useState("");
  const [auditUserFilter, setAuditUserFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [status, setStatus] = useState("");
  const [isBusy, setBusy] = useState(false);
  const [verifyResults, setVerifyResults] = useState<Record<number, VerifyResult>>({});

  const selectedDocumentName = useMemo(() => {
    return documents.find((doc) => String(doc.id) === documentId)?.filename ?? "All documents";
  }, [documents, documentId]);

  async function loadDocuments() {
    const response = await fetch(`${API_URL}/documents`);
    setDocuments(await response.json());
  }

  async function loadLogs() {
    const params = new URLSearchParams();
    if (searchText) params.set("text", searchText);
    if (auditUserFilter) params.set("user_id", auditUserFilter);
    if (documentId) params.set("document_id", documentId);
    if (fromDate) params.set("from_date", `${fromDate}T00:00:00`);
    if (toDate) params.set("to_date", `${toDate}T23:59:59`);
    const response = await fetch(`${API_URL}/audit-logs?${params}`);
    setLogs(await response.json());
  }

  useEffect(() => {
    loadDocuments().catch(() => setStatus("Backend is not reachable yet."));
    loadLogs().catch(() => undefined);
  }, []);

  async function uploadPdf(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setStatus("Uploading and indexing PDF...");
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_URL}/documents/upload`, {
      method: "POST",
      body: formData
    });
    if (!response.ok) {
      setStatus("Upload failed. Make sure the file is a PDF.");
    } else {
      setFile(null);
      setStatus("PDF indexed and ready for RAG chat.");
      await loadDocuments();
    }
    setBusy(false);
  }

  async function askQuestion(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setStatus("Retrieving chunks and generating audit hash...");
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        user_id: userId || "anonymous",
        document_id: documentId ? Number(documentId) : null
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      setStatus(payload.detail ?? "Chat request failed.");
    } else {
      setChatResult(payload);
      setStatus("Answer logged with SHA256 verification hash.");
      await loadLogs();
    }
    setBusy(false);
  }

  async function verifyLog(id: number) {
    const response = await fetch(`${API_URL}/audit-logs/${id}/verify`);
    const payload = await response.json();
    if (response.ok) {
      setVerifyResults((current) => ({ ...current, [id]: payload }));
    }
  }

  function exportLogs(format: "json" | "csv") {
    window.open(`${API_URL}/audit-logs/export?format=${format}`, "_blank");
  }

  return (
    <main className="min-h-screen bg-[#f6f7f2] text-[#16201b]">
      <div className="border-b border-[#cfd7c6] bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <div>
            <h1 className="text-xl font-semibold">AI Audit Trail Middleware</h1>
            <p className="text-sm text-[#5c665d]">RAG chat with verifiable retrieval logs</p>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-[#cfd7c6] px-3 py-2 text-sm">
            <ShieldCheck size={18} />
            SHA256 enabled
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-5 px-5 py-5 lg:grid-cols-[360px_1fr]">
        <aside className="space-y-5">
          <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
            <div className="mb-3 flex items-center gap-2">
              <Upload size={18} />
              <h2 className="font-semibold">Upload PDFs</h2>
            </div>
            <form className="space-y-3" onSubmit={uploadPdf}>
              <input
                className="w-full rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
                type="file"
                accept="application/pdf"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <button
                className="flex w-full items-center justify-center gap-2 rounded-md bg-[#245d45] px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
                disabled={!file || isBusy}
              >
                <Upload size={16} />
                Index document
              </button>
            </form>
          </section>

          <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
            <div className="mb-3 flex items-center gap-2">
              <FileText size={18} />
              <h2 className="font-semibold">Documents</h2>
            </div>
            <select
              className="mb-3 w-full rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
            >
              <option value="">All documents</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            <div className="space-y-2">
              {documents.map((doc) => (
                <div key={doc.id} className="rounded-md border border-[#e1e6dc] p-3 text-sm">
                  <div className="font-medium">{doc.filename}</div>
                  <div className="text-[#5c665d]">
                    {doc.chunk_count} chunks &middot; {formatDate(doc.uploaded_at)}
                  </div>
                </div>
              ))}
              {!documents.length && <p className="text-sm text-[#5c665d]">No PDFs indexed yet.</p>}
            </div>
          </section>
        </aside>

        <div className="space-y-5">
          <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold">RAG Chat</h2>
                <p className="text-sm text-[#5c665d]">Scope: {selectedDocumentName}</p>
              </div>
              <input
                className="w-52 rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="User ID"
              />
            </div>
            <form className="flex gap-2" onSubmit={askQuestion}>
              <input
                className="min-w-0 flex-1 rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask a question from the uploaded documents"
              />
              <button
                className="flex items-center gap-2 rounded-md bg-[#245d45] px-4 py-2 font-medium text-white disabled:opacity-60"
                disabled={isBusy}
              >
                <Send size={17} />
                Ask
              </button>
            </form>
            {status && <p className="mt-3 text-sm text-[#5c665d]">{status}</p>}

            {chatResult && (
              <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_360px]">
                <div className="rounded-md border border-[#e1e6dc] p-4">
                  <div className="mb-2 text-sm text-[#5c665d]">{chatResult.model}</div>
                  <p className="whitespace-pre-wrap leading-7">{chatResult.response}</p>
                </div>
                <div className="rounded-md border border-[#e1e6dc] p-4">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                    <CheckCircle2 size={17} />
                    Audit record #{chatResult.audit_log_id}
                  </div>
                  <div className="break-all rounded-md bg-[#eef2e9] p-3 font-mono text-xs">
                    {chatResult.sha256_hash}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {chatResult.pii_masked && (
                      <span className="rounded-md border border-[#cfd7c6] px-2 py-1 text-xs">PII masked</span>
                    )}
                    {chatResult.alerts.map((alert) => (
                      <span
                        className="inline-flex items-center gap-1 rounded-md border border-[#e0b15f] bg-[#fff7e6] px-2 py-1 text-xs text-[#6f4b00]"
                        key={alert}
                      >
                        <AlertTriangle size={13} />
                        {alert}
                      </span>
                    ))}
                  </div>
                  <div className="mt-3 text-sm text-[#5c665d]">{formatDate(chatResult.timestamp)}</div>
                </div>
              </div>
            )}
          </section>

          <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <History size={18} />
                <h2 className="font-semibold">Audit Dashboard</h2>
              </div>
              <div className="flex gap-2">
                <button
                  className="flex items-center gap-2 rounded-md border border-[#bcc8ba] px-3 py-2 text-sm"
                  onClick={() => exportLogs("json")}
                  type="button"
                >
                  <Download size={16} />
                  JSON
                </button>
                <button
                  className="flex items-center gap-2 rounded-md border border-[#bcc8ba] px-3 py-2 text-sm"
                  onClick={() => exportLogs("csv")}
                  type="button"
                >
                  <Download size={16} />
                  CSV
                </button>
              </div>
              <form
                className="grid w-full gap-2 md:grid-cols-[1fr_160px_150px_150px_44px]"
                onSubmit={(event) => {
                  event.preventDefault();
                  loadLogs();
                }}
              >
                <input
                  className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  placeholder="Search query or answer"
                />
                <input
                  className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
                  value={auditUserFilter}
                  onChange={(event) => setAuditUserFilter(event.target.value)}
                  placeholder="User ID"
                />
                <input
                  className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
                  value={fromDate}
                  onChange={(event) => setFromDate(event.target.value)}
                  type="date"
                />
                <input
                  className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
                  value={toDate}
                  onChange={(event) => setToDate(event.target.value)}
                  type="date"
                />
                <button className="rounded-md border border-[#bcc8ba] px-3 py-2" title="Search audit logs">
                  <Search size={17} />
                </button>
              </form>
            </div>

            <div className="space-y-3">
              {logs.map((log) => (
                <article key={log.id} className="rounded-md border border-[#e1e6dc] p-4">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm text-[#5c665d]">
                    <span>
                      #{log.id} &middot; {log.user_id} &middot; {formatDate(log.timestamp)}
                    </span>
                    <span>{log.document_name ?? "All documents"}</span>
                  </div>
                  <h3 className="font-semibold">{log.query}</h3>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#354239]">{log.response}</p>
                  <div className="mt-3 break-all rounded-md bg-[#eef2e9] p-2 font-mono text-xs">
                    {log.sha256_hash}
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {log.pii_masked && (
                      <span className="rounded-md border border-[#cfd7c6] px-2 py-1 text-xs">PII masked</span>
                    )}
                    {log.alerts.map((alert) => (
                      <span
                        className="inline-flex items-center gap-1 rounded-md border border-[#e0b15f] bg-[#fff7e6] px-2 py-1 text-xs text-[#6f4b00]"
                        key={`${log.id}-${alert}`}
                      >
                        <AlertTriangle size={13} />
                        {alert}
                      </span>
                    ))}
                    <button
                      className="ml-auto flex items-center gap-2 rounded-md border border-[#bcc8ba] px-3 py-2 text-sm"
                      onClick={() => verifyLog(log.id)}
                      type="button"
                    >
                      <ShieldCheck size={16} />
                      Verify
                    </button>
                  </div>
                  {verifyResults[log.id] && (
                    <div
                      className={`mt-2 rounded-md px-3 py-2 text-sm ${
                        verifyResults[log.id].verified
                          ? "bg-[#e8f4e9] text-[#1f5d35]"
                          : "bg-[#fff0ed] text-[#8a2d20]"
                      }`}
                    >
                      {verifyResults[log.id].verified ? "Verified: hash matches" : "Tampered: hash mismatch"}
                    </div>
                  )}
                  <details className="mt-3 text-sm">
                    <summary className="cursor-pointer font-medium">Retrieved sources</summary>
                    <div className="mt-2 space-y-2">
                      {log.retrieved_chunks.map((chunk, index) => (
                        <div key={`${log.id}-${index}`} className="rounded-md bg-[#fbfcf8] p-3">
                          <div className="mb-1 text-xs font-semibold text-[#5c665d]">
                            {chunk.filename}, page {chunk.page}, score {chunk.score ?? "n/a"}
                          </div>
                          <p className="leading-6">{chunk.text}</p>
                        </div>
                      ))}
                    </div>
                  </details>
                </article>
              ))}
              {!logs.length && <p className="text-sm text-[#5c665d]">No audit logs yet.</p>}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
