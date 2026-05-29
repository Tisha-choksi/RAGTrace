import { FileText } from "lucide-react";
import { formatDate } from "../utils";
import type { DocumentItem } from "../types";

type Props = {
  documents: DocumentItem[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export function DocumentList({ documents, selectedId, onSelect }: Props) {
  return (
    <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <FileText size={18} />
        <h2 className="font-semibold">Documents</h2>
      </div>
      <select
        className="mb-3 w-full rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
        value={selectedId}
        onChange={(e) => onSelect(e.target.value)}
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
  );
}
