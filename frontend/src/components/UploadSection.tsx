import { FormEvent, useState } from "react";
import { Upload } from "lucide-react";
import { uploadPdf } from "../api";
import type { DocumentItem } from "../types";

type Props = {
  isBusy: boolean;
  onUploaded: (doc: DocumentItem) => void;
  onError: (message: string) => void;
  setStatus: (s: string) => void;
};

export function UploadSection({ isBusy, onUploaded, onError, setStatus }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setStatus("Uploading and indexing PDF...");
    try {
      const doc = await uploadPdf(file);
      setFile(null);
      setStatus("PDF indexed and ready for RAG chat.");
      onUploaded(doc);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-md border border-[#cfd7c6] bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <Upload size={18} />
        <h2 className="font-semibold">Upload PDFs</h2>
      </div>
      <form className="space-y-3" onSubmit={handleSubmit}>
        <input
          className="w-full rounded-md border border-[#bcc8ba] bg-[#fbfcf8] px-3 py-2 text-sm"
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          className="flex w-full items-center justify-center gap-2 rounded-md bg-[#245d45] px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          disabled={!file || busy || isBusy}
        >
          <Upload size={16} />
          Index document
        </button>
      </form>
    </section>
  );
}
