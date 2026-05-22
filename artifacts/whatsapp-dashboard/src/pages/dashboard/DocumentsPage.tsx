import React, { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UploadCloud, FileText, Trash2, CheckCircle, AlertCircle,
  Clock, Loader2, FileSpreadsheet, FileType2,
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface Doc {
  id: string;
  filename: string;
  file_type: string;
  chunk_count: number;
  status: string;
  created_at: string;
}

function FileIcon({ type }: { type: string }) {
  if (type === "xlsx") return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
  if (type === "docx") return <FileType2 className="w-5 h-5 text-blue-400" />;
  return <FileText className="w-5 h-5 text-violet-400" />;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
    ready: { label: "جاهز", className: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: <CheckCircle className="w-3.5 h-3.5" /> },
    processing: { label: "معالجة...", className: "bg-blue-500/10 text-blue-400 border-blue-500/20", icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
    error: { label: "خطأ", className: "bg-red-500/10 text-red-400 border-red-500/20", icon: <AlertCircle className="w-3.5 h-3.5" /> },
  };
  const s = map[status] ?? { label: status, className: "bg-slate-700 text-slate-400 border-slate-600", icon: <Clock className="w-3.5 h-3.5" /> };
  return (
    <span className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full border ${s.className}`}>
      {s.icon} {s.label}
    </span>
  );
}

export default function DocumentsPage() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const { data, isLoading } = useQuery<{ documents: Doc[] }>({
    queryKey: ["documents"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/documents`, { credentials: "include" });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
  });

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("company_id", "default");
      const res = await fetch(`${BASE}/api/v1/upload`, { method: "POST", credentials: "include", body: fd });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "فشل الرفع");
      return json;
    },
    onSuccess: (d) => {
      setUploadMsg({ ok: true, text: d.message });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e: Error) => setUploadMsg({ ok: false, text: e.message }),
  });

  const deleteMut = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${BASE}/api/v1/documents/${id}`, { method: "DELETE", credentials: "include" });
      if (!res.ok) throw new Error("فشل الحذف");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploadMsg(null);
    Array.from(files).forEach((f) => uploadMut.mutate(f));
  }

  return (
    <div className="p-8 space-y-8" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-100">قاعدة المعرفة</h1>
        <p className="text-slate-400 text-sm mt-1">ارفع مستنداتك وسيقرأها نصيح ويجيب عنها فوراً</p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200
          ${dragOver ? "border-emerald-500 bg-emerald-500/5" : "border-slate-700 hover:border-emerald-500/50 hover:bg-slate-800/30"}`}
      >
        <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.txt,.xlsx" className="hidden"
          onChange={(e) => handleFiles(e.target.files)} />
        {uploadMut.isPending ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
            <p className="text-slate-300 font-medium">جاري المعالجة والحفظ في ChromaDB...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <UploadCloud className="w-10 h-10 text-slate-500" />
            <p className="text-slate-300 font-medium">اسحب ملفاتك هنا أو اضغط للاختيار</p>
            <p className="text-slate-500 text-sm">PDF · DOCX · TXT · XLSX</p>
          </div>
        )}
      </div>

      {uploadMsg && (
        <div className={`flex items-start gap-3 rounded-xl px-4 py-3 border ${
          uploadMsg.ok ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : "bg-red-500/10 border-red-500/20 text-red-400"
        }`}>
          {uploadMsg.ok ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
          <p className="text-sm">{uploadMsg.text}</p>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-bold text-slate-100">المستندات المرفوعة</h2>
          <span className="text-slate-500 text-sm">{data?.documents?.length ?? 0} ملف</span>
        </div>
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
          </div>
        ) : !data?.documents?.length ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <FileText className="w-10 h-10 text-slate-700" />
            <p className="text-slate-500 text-sm">لا توجد مستندات بعد — ارفع ملفك الأول</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {data.documents.map((doc) => (
              <div key={doc.id} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-800/30 transition-colors">
                <FileIcon type={doc.file_type} />
                <div className="flex-1 min-w-0">
                  <p className="text-slate-200 font-medium text-sm truncate">{doc.filename}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{doc.chunk_count} قطعة · {new Date(doc.created_at).toLocaleDateString("ar-SA")}</p>
                </div>
                <StatusBadge status={doc.status} />
                <button onClick={() => deleteMut.mutate(doc.id)} disabled={deleteMut.isPending}
                  className="p-2 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
