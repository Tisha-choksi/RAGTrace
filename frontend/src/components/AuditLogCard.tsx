import { AlertTriangle, ShieldCheck } from "lucide-react";
import { formatDate } from "../utils";
import type { AuditLog, VerifyResult } from "../types";

type Props = {
  log: AuditLog;
  verifyResult?: VerifyResult;
  onVerify: (id: number) => void;
};

export function AuditLogCard({ log, verifyResult, onVerify }: Props) {
  return (
    <article className="rounded-md border border-[#e1e6dc] p-4">
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
        {log.groundedness_score != null && (() => {
          const pct = Math.round(log.groundedness_score! * 100);
          const cls =
            log.groundedness_score! >= 0.7
              ? "border-green-300 bg-green-50 text-green-800"
              : log.groundedness_score! >= 0.4
                ? "border-yellow-300 bg-yellow-50 text-yellow-800"
                : "border-red-300 bg-red-50 text-red-800";
          return (
            <span className={`rounded-md border px-2 py-1 text-xs ${cls}`}>
              Grounded {pct}%
            </span>
          );
        })()}
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
          onClick={() => onVerify(log.id)}
          type="button"
        >
          <ShieldCheck size={16} />
          Verify
        </button>
      </div>
      {verifyResult && (
        <div
          className={`mt-2 rounded-md px-3 py-2 text-sm ${
            verifyResult.verified
              ? "bg-[#e8f4e9] text-[#1f5d35]"
              : "bg-[#fff0ed] text-[#8a2d20]"
          }`}
        >
          {verifyResult.verified ? "Verified: hash matches" : "Tampered: hash mismatch"}
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
  );
}
