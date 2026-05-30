import { FormEvent, useState } from "react";
import { AlertTriangle, CheckCircle2, Send } from "lucide-react";
import { sendQuestion } from "../api";
import { formatDate } from "../utils";
import type { ChatResult } from "../types";

type Props = {
  selectedDocumentName: string;
  documentId: string;
  status: string;
  isBusy: boolean;
  setStatus: (s: string) => void;
  setBusy: (b: boolean) => void;
  onNewLog: () => void;
};

export function ChatSection({
  selectedDocumentName,
  documentId,
  status,
  isBusy,
  setStatus,
  setBusy,
  onNewLog,
}: Props) {
  const [userId, setUserId] = useState("demo-user");
  const [query, setQuery] = useState("");
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setStatus("Retrieving chunks and generating audit hash...");
    try {
      const result = await sendQuestion({ query, userId, documentId: documentId || null });
      setChatResult(result);
      setStatus("Answer logged with SHA256 verification hash.");
      onNewLog();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Chat request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">RAG Chat</h2>
          <p className="text-sm text-[#5c665d]">Scope: {selectedDocumentName}</p>
        </div>
        <input
          className="w-52 rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="User ID"
        />
      </div>
      <form className="flex gap-2" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
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
                <span className="rounded-md border border-[#cfd7c6] px-2 py-1 text-xs">
                  PII masked
                </span>
              )}
              {chatResult.alerts.map((alert, i) => (
                <span
                  className="inline-flex items-center gap-1 rounded-md border border-[#e0b15f] bg-[#fff7e6] px-2 py-1 text-xs text-[#6f4b00]"
                  key={i}
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
  );
}
