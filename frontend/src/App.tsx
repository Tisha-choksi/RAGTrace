import React, { useEffect, useMemo, useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { createRoot } from "react-dom/client";
import "./main.css";

import { fetchDocuments, fetchLogs, verifyLog } from "./api";
import { DocumentList } from "./components/DocumentList";
import { UploadSection } from "./components/UploadSection";
import { ChatSection } from "./components/ChatSection";
import { AuditDashboard } from "./components/AuditDashboard";
import type { DocumentItem, LogFilters, PaginatedLogs, VerifyResult } from "./types";

const PAGE_SIZE = 50;

const EMPTY_LOGS: PaginatedLogs = { items: [], total: 0, limit: PAGE_SIZE, offset: 0 };
const EMPTY_FILTERS: LogFilters = { searchText: "", auditUserFilter: "", fromDate: "", toDate: "", offset: 0 };

function App() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [paginatedLogs, setPaginatedLogs] = useState<PaginatedLogs>(EMPTY_LOGS);
  const [documentId, setDocumentId] = useState("");
  const [status, setStatus] = useState("");
  const [isBusy, setBusy] = useState(false);
  const [verifyResults, setVerifyResults] = useState<Record<number, VerifyResult>>({});
  const [logFilters, setLogFilters] = useState<LogFilters>(EMPTY_FILTERS);
  const logFiltersRef = useRef(logFilters);
  logFiltersRef.current = logFilters;

  const selectedDocumentName = useMemo(
    () => documents.find((doc) => String(doc.id) === documentId)?.filename ?? "All documents",
    [documents, documentId]
  );

  async function loadLogs(filters: LogFilters = logFilters) {
    const result = await fetchLogs({ ...filters, documentId, limit: PAGE_SIZE });
    setPaginatedLogs(result);
  }

  useEffect(() => {
    fetchDocuments()
      .then(setDocuments)
      .catch(() => setStatus("Backend is not reachable yet."));
    loadLogs().catch(() => setStatus("Failed to load audit logs."));
  }, []);

  useEffect(() => {
    loadLogs(logFiltersRef.current).catch(() => {});
  }, [documentId]);

  async function handleVerify(id: number) {
    const result = await verifyLog(id);
    setVerifyResults((prev) => ({ ...prev, [id]: result }));
  }

  function handleSearch(filters: LogFilters) {
    setLogFilters(filters);
    loadLogs(filters).catch(() => setStatus("Failed to load audit logs."));
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
          <UploadSection
            isBusy={isBusy}
            onUploaded={(doc) => setDocuments((prev) => [doc, ...prev])}
            onError={setStatus}
            setStatus={setStatus}
          />
          <DocumentList
            documents={documents}
            selectedId={documentId}
            onSelect={setDocumentId}
          />
        </aside>

        <div className="space-y-5">
          <ChatSection
            selectedDocumentName={selectedDocumentName}
            documentId={documentId}
            status={status}
            isBusy={isBusy}
            setStatus={setStatus}
            setBusy={setBusy}
            onNewLog={() => loadLogs().catch(() => {})}
          />
          <AuditDashboard
            logs={paginatedLogs.items}
            total={paginatedLogs.total}
            limit={paginatedLogs.limit}
            offset={paginatedLogs.offset}
            verifyResults={verifyResults}
            onSearch={handleSearch}
            onVerify={handleVerify}
          />
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
