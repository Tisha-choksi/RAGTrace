import { FormEvent, useState } from "react";
import { Download, History, Search } from "lucide-react";
import { exportLogs } from "../api";
import { AuditLogCard } from "./AuditLogCard";
import type { AuditLog, LogFilters, VerifyResult } from "../types";

type Props = {
  logs: AuditLog[];
  total: number;
  limit: number;
  offset: number;
  verifyResults: Record<number, VerifyResult>;
  onSearch: (filters: LogFilters) => void;
  onVerify: (id: number) => void;
};

export function AuditDashboard({ logs, total, limit, offset, verifyResults, onSearch, onVerify }: Props) {
  const [searchText, setSearchText] = useState("");
  const [auditUserFilter, setAuditUserFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  function filtersAt(newOffset: number): LogFilters {
    return { searchText, auditUserFilter, fromDate, toDate, offset: newOffset };
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    onSearch(filtersAt(0));
  }

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <History size={18} />
          <h2 className="font-semibold">Audit Dashboard</h2>
          {total > 0 && (
            <span className="rounded-full bg-[#eef2e9] px-2 py-0.5 text-xs text-[#5c665d]">
              {total} total
            </span>
          )}
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
          onSubmit={handleSearch}
        >
          <input
            className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search query or answer"
          />
          <input
            className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
            value={auditUserFilter}
            onChange={(e) => setAuditUserFilter(e.target.value)}
            placeholder="User ID"
          />
          <input
            className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            type="date"
          />
          <input
            className="rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            type="date"
          />
          <button className="rounded-md border border-[#bcc8ba] px-3 py-2" title="Search audit logs">
            <Search size={17} />
          </button>
        </form>
      </div>

      <div className="space-y-3">
        {logs.map((log) => (
          <AuditLogCard
            key={log.id}
            log={log}
            verifyResult={verifyResults[log.id]}
            onVerify={onVerify}
          />
        ))}
        {!logs.length && <p className="text-sm text-[#5c665d]">No audit logs yet.</p>}
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="text-[#5c665d]">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              className="rounded-md border border-[#bcc8ba] px-3 py-1.5 disabled:opacity-40"
              disabled={offset === 0}
              onClick={() => onSearch(filtersAt(Math.max(0, offset - limit)))}
              type="button"
            >
              Previous
            </button>
            <button
              className="rounded-md border border-[#bcc8ba] px-3 py-1.5 disabled:opacity-40"
              disabled={offset + limit >= total}
              onClick={() => onSearch(filtersAt(offset + limit))}
              type="button"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
