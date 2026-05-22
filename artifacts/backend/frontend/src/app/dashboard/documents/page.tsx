"use client";

import React, { useState, useRef } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  UploadCloud, 
  FileText, 
  Trash2, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  RefreshCw, 
  FileSpreadsheet, 
  FileArchive, 
  Plus,
  Loader2 
} from "lucide-react";

interface DocumentItem {
  id: string;
  file_name: string;
  file_type: string;
  status: "queued" | "processing" | "ready" | "failed";
  chunk_count: number | null;
  uploaded_at: string;
  processed_at: string | null;
}

export default function DocumentsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  
  // Upload States
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const tenantId = user?.tenant_id;

  // Fetch Documents
  const { data: documents = [], isLoading } = useQuery<DocumentItem[]>({
    queryKey: ["documents", tenantId],
    queryFn: async () => {
      if (!tenantId) return [];
      const res = await fetch(`/api/v1/tenants/${tenantId}/documents`);
      if (!res.ok) throw new Error("فشل في جلب قائمة المستندات");
      return res.json();
    },
    enabled: !!tenantId,
    // Poll every 5s if there is any document currently in queued or processing status
    refetchInterval: (query) => {
      const docs = query.state.data as DocumentItem[] | undefined;
      const hasPending = docs?.some(d => d.status === "queued" || d.status === "processing");
      return hasPending ? 5000 : false;
    }
  });

  // Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: async (docId: string) => {
      const res = await fetch(`/api/v1/tenants/${tenantId}/documents/${docId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("فشل في حذف المستند");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", tenantId] });
      setSuccessMsg("تم حذف المستند بنجاح.");
      setTimeout(() => setSuccessMsg(""), 3000);
    },
    onError: (err: Error) => {
      setErrorMsg(err.message || "حدث خطأ أثناء حذف المستند");
    }
  });

  // File Validation & Upload Logic
  const handleUpload = async (file: File) => {
    setErrorMsg("");
    setSuccessMsg("");
    
    // Check format
    const allowedExtensions = ["pdf", "docx", "txt", "xlsx"];
    const fileExt = file.name.split(".").pop()?.toLowerCase() || "";
    
    if (!allowedExtensions.includes(fileExt)) {
      setErrorMsg("صيغة الملف غير مدعومة. الصيغ المسموح بها هي: PDF, DOCX, TXT, XLSX");
      return;
    }

    // Check size (50MB)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      setErrorMsg("حجم الملف يتجاوز الحد الأقصى المسموح به (50 ميجابايت).");
      return;
    }

    setUploading(true);
    setUploadProgress(10); // Start progress indication

    try {
      const formData = new FormData();
      formData.append("file", file);

      // Simulate step-wise upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => (prev >= 80 ? prev : prev + 10));
      }, 300);

      const res = await fetch(`/api/v1/tenants/${tenantId}/documents`, {
        method: "POST",
        body: formData,
      });

      clearInterval(progressInterval);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "فشل رفع الملف" }));
        throw new Error(errorData.detail || "حدث خطأ أثناء رفع المستند");
      }

      setUploadProgress(100);
      setSuccessMsg("تم رفع الملف بنجاح. جاري تحليل وفهرسة المستند...");
      queryClient.invalidateQueries({ queryKey: ["documents", tenantId] });
      
      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        setSuccessMsg("");
      }, 3000);

    } catch (err) {
      const error = err as Error;
      setErrorMsg(error.message || "فشل رفع الملف. يرجى التحقق من الاتصال بالشبكة.");
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleUpload(e.target.files[0]);
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  // Status Badge Helper
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ready":
        return (
          <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20 font-medium">
            <CheckCircle className="w-3.5 h-3.5" /> جاهز
          </span>
        );
      case "processing":
        return (
          <span className="flex items-center gap-1.5 text-xs text-blue-400 bg-blue-500/10 px-2.5 py-1 rounded-full border border-blue-500/20 font-medium animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> معالجة
          </span>
        );
      case "queued":
        return (
          <span className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full border border-slate-700 font-medium">
            <Clock className="w-3.5 h-3.5" /> في الانتظار
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1.5 text-xs text-rose-400 bg-rose-500/10 px-2.5 py-1 rounded-full border border-rose-500/20 font-medium">
            <AlertCircle className="w-3.5 h-3.5" /> فشل التحليل
          </span>
        );
      default:
        return null;
    }
  };

  // File Icon Helper
  const getFileIcon = (fileName: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    if (ext === "xlsx" || ext === "xls") return <FileSpreadsheet className="w-8 h-8 text-emerald-500" />;
    if (ext === "pdf") return <FileArchive className="w-8 h-8 text-rose-500" />;
    return <FileText className="w-8 h-8 text-blue-400" />;
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100">قاعدة المعرفة والمستندات</h1>
          <p className="text-sm text-slate-400 mt-1">قم برفع مستندات عملك (كتالوجات، سياسات، أسئلة شائعة) لتدريب الذكاء الاصطناعي على الإجابة منها.</p>
        </div>
        <button
          onClick={triggerFileSelect}
          disabled={uploading}
          className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-5 py-2.5 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/10 transition-all duration-200 shrink-0"
        >
          <Plus className="w-5 h-5 stroke-[2.5]" />
          <span>إضافة مستند جديد</span>
        </button>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt,.xlsx"
          className="hidden"
        />
      </div>

      {/* Alerts */}
      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3 text-rose-400 text-sm animate-fade-in">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-start gap-3 text-emerald-400 text-sm animate-fade-in">
          <CheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Upload Drag & Drop Area */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={triggerFileSelect}
        className={`border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all duration-300 ${
          dragActive
            ? "border-emerald-500 bg-emerald-500/[0.03]"
            : "border-slate-800 bg-slate-900/30 hover:border-slate-700 hover:bg-slate-900/50"
        } ${uploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <div className="w-14 h-14 bg-slate-800 rounded-2xl flex items-center justify-center text-slate-400 border border-slate-700">
          {uploading ? (
            <RefreshCw className="w-7 h-7 text-emerald-500 animate-spin" />
          ) : (
            <UploadCloud className="w-7 h-7" />
          )}
        </div>
        <div className="text-center">
          <p className="font-bold text-slate-200">اسحب الملف وأفلته هنا، أو اضغط للتصفح</p>
          <p className="text-xs text-slate-500 mt-1">تنسيقات الملفات المعتمدة: PDF, DOCX, TXT, XLSX (الحد الأقصى للملف: 50 ميجابايت)</p>
        </div>

        {uploading && (
          <div className="w-full max-w-xs mt-2 space-y-2">
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-[10px] text-slate-500 text-center">جاري رفع الملف... {uploadProgress}%</p>
          </div>
        )}
      </div>

      {/* Documents Table / List */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
        <div className="px-6 py-5 border-b border-slate-800 flex items-center justify-between">
          <h3 className="font-bold text-slate-200">ملفات المعرفة الخاصة بك</h3>
          <span className="text-xs text-slate-500 font-mono">إجمالي المستندات: {documents.length}</span>
        </div>

        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            <span className="text-sm text-slate-400">جاري تحميل المستندات...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="py-20 text-center">
            <FileText className="w-12 h-12 text-slate-700 mx-auto mb-3" />
            <p className="font-bold text-slate-400">لا توجد مستندات مرفوعة حالياً</p>
            <p className="text-xs text-slate-600 mt-1">ابدأ برفع مستندك الأول لتغذية قاعدة معلومات النظام.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right border-collapse text-sm">
              <thead>
                <tr className="bg-slate-900/80 text-slate-400 text-xs font-semibold uppercase border-b border-slate-800">
                  <th className="px-6 py-4">اسم المستند</th>
                  <th className="px-6 py-4">تاريخ الرفع</th>
                  <th className="px-6 py-4">الأقسام المستخرجة (Chunks)</th>
                  <th className="px-6 py-4">حالة المعالجة</th>
                  <th className="px-6 py-4 text-left">إجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-900/30 transition-colors duration-150">
                    <td className="px-6 py-4 flex items-center gap-3">
                      {getFileIcon(doc.file_name)}
                      <div>
                        <span className="font-bold text-slate-200 block max-w-xs truncate">{doc.file_name}</span>
                        <span className="text-[10px] text-slate-500 font-mono uppercase">{doc.file_type}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-xs font-mono">
                      {new Date(doc.uploaded_at).toLocaleString("ar-EG", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-6 py-4 text-slate-300 font-mono">
                      {doc.chunk_count !== null ? doc.chunk_count : "—"}
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(doc.status)}</td>
                    <td className="px-6 py-4 text-left">
                      <button
                        onClick={() => {
                          if (confirm("هل أنت متأكد من رغبتك في حذف هذا المستند نهائياً؟ سيتم إلغاء تدريب الذكاء الاصطناعي عليه.")) {
                            deleteMutation.mutate(doc.id);
                          }
                        }}
                        disabled={deleteMutation.isPending && deleteMutation.variables === doc.id}
                        className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-xl transition-all duration-200 disabled:opacity-50"
                        title="حذف المستند"
                      >
                        {deleteMutation.isPending && deleteMutation.variables === doc.id ? (
                          <RefreshCw className="w-5 h-5 animate-spin" />
                        ) : (
                          <Trash2 className="w-5 h-5" />
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
