import { FormEvent, useState } from "react";
import { AlertTriangle, CheckCircle2, Send } from "lucide-react";
import { streamQuestion } from "../api";
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

function GroundednessBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const [colorClass, label] =
    score >= 0.7
      ? ["border-green-300 bg-green-50 text-green-800", `Grounded ${pct}%`]
      : score >= 0.4
        ? ["border-yellow-300 bg-yellow-50 text-yellow-800", `Partial groundedness ${pct}%`]
        : ["border-red-300 bg-red-50 text-red-800", `Low groundedness ${pct}%`];
  return (
    <span className={`rounded-md border px-2 py-1 text-xs ${colorClass}`}>{label}</span>
  );
}

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
  const [streamingText, setStreamingText] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setChatResult(null);
    setStreamingText("");
    setStatus("Retrieving context with hybrid search…");
    try {
      const result = await streamQuestion(
        { query, userId, documentId: documentId || null },
        (token) => {
          setStreamingText((prev) => prev + token);
          setStatus("Generating response…");
        },
      );
      setChatResult(result);
      setStreamingText("");
      setStatus("Answer logged with SHA256 verification hash.");
      onNewLog();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Chat request failed.");
    } finally {
      setBusy(false);
    }
  }

  const displayText = streamingText || (chatResult?.response ?? "");
  const isStreaming = isBusy && streamingText.length > 0;

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

      {displayText && (
        <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_360px]">
          <div className="rounded-md border border-[#e1e6dc] p-4">
            <div className="mb-2 text-sm text-[#5c665d]">
              {chatResult?.model ?? "Generating…"}
            </div>
            <p className="whitespace-pre-wrap leading-7">
              {displayText}
              {isStreaming && (
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-[#245d45]" />
              )}
            </p>
          </div>

          {chatResult && (
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
                {chatResult.groundedness_score != null && (
                  <GroundednessBadge score={chatResult.groundedness_score} />
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
          )}
        </div>
      )}
    </section>
  );
}
