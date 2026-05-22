import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Settings, Key, Save, Loader2, CheckCircle, AlertCircle, Eye, EyeOff,
  BarChart3, Building2, MessageSquare, FileText, Bot, Info
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const PLAN_LIMITS = [
  { tier: "free",     label: "مجاني",   price: "$0",  msgs: "50",      color: "text-slate-400",  bg: "bg-slate-500/10 border-slate-500/20" },
  { tier: "starter",  label: "Starter", price: "$9",  msgs: "500",     color: "text-blue-400",   bg: "bg-blue-500/10 border-blue-500/20" },
  { tier: "pro",      label: "Pro",     price: "$19", msgs: "2,000",   color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
  { tier: "business", label: "Business",price: "$39", msgs: "غير محدود", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20" },
];

export default function SystemSettingsPage() {
  const queryClient = useQueryClient();
  const [openaiKey, setOpenaiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const { data: settings, isLoading: loadingSettings } = useQuery<Record<string, string>>({
    queryKey: ["super-admin-settings"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/super-admin/settings`, { credentials: "include" });
      if (!res.ok) throw new Error("فشل في تحميل الإعدادات");
      return res.json();
    },
  });

  const { data: stats } = useQuery<{ tenants: number; conversations: number; documents: number }>({
    queryKey: ["super-admin-stats"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/super-admin/stats`, { credentials: "include" });
      if (!res.ok) return { tenants: 0, conversations: 0, documents: 0 };
      return res.json();
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${BASE}/api/super-admin/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ openai_api_key: openaiKey }),
      });
      if (!res.ok) throw new Error("فشل في حفظ الإعدادات");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin-settings"] });
      setOpenaiKey("");
      setSuccessMsg("تم حفظ مفتاح OpenAI API بنجاح.");
      setTimeout(() => setSuccessMsg(""), 4000);
    },
    onError: (err: Error) => {
      setErrorMsg(err.message || "حدث خطأ أثناء الحفظ");
      setTimeout(() => setErrorMsg(""), 4000);
    },
  });

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!openaiKey.trim()) { setErrorMsg("يرجى إدخال مفتاح API."); return; }
    setErrorMsg("");
    setSuccessMsg("");
    saveMutation.mutate();
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          <Settings className="w-6 h-6 text-violet-400" />
          إعدادات النظام
        </h1>
        <p className="text-slate-500 text-sm mt-1">إدارة مفاتيح API، حدود الخطط، وإحصائيات المنصة</p>
      </div>

      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { icon: Building2, label: "إجمالي الشركات", value: stats.tenants, color: "text-violet-400", bg: "bg-violet-500/10" },
            { icon: MessageSquare, label: "إجمالي المحادثات", value: stats.conversations, color: "text-emerald-400", bg: "bg-emerald-500/10" },
            { icon: FileText, label: "إجمالي المستندات", value: stats.documents, color: "text-blue-400", bg: "bg-blue-500/10" },
          ].map((s) => (
            <div key={s.label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <div className={`w-9 h-9 ${s.bg} rounded-xl flex items-center justify-center mb-3`}>
                <s.icon className={`w-5 h-5 ${s.color}`} />
              </div>
              <p className={`text-2xl font-extrabold ${s.color}`}>{(s.value ?? 0).toLocaleString()}</p>
              <p className="text-xs text-slate-500 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-violet-400" />
          حدود خطط الاشتراك
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {PLAN_LIMITS.map((p) => (
            <div key={p.tier} className={`p-4 rounded-2xl border ${p.bg}`}>
              <p className={`text-xs font-bold ${p.color}`}>{p.label}</p>
              <p className="text-xl font-extrabold text-slate-100 mt-1">{p.price}<span className="text-[10px] text-slate-500 font-normal">/شهر</span></p>
              <p className="text-[11px] text-slate-500 mt-1">{p.msgs} محادثة/شهر</p>
            </div>
          ))}
        </div>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-start gap-3 text-emerald-400 text-sm">
          <CheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3 text-rose-400 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSave}>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Key className="w-5 h-5 text-violet-400" />
            <span>مفتاح OpenAI API</span>
          </h2>

          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex items-start gap-2.5 text-xs text-slate-400 leading-relaxed">
            <Info className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
            <span>
              هذا المفتاح يُستخدم لتشغيل نموذج GPT-4o mini ونظام RAG لجميع الشات بوتات في المنصة.
              احصل على مفتاحك من{" "}
              <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer"
                className="text-violet-400 hover:underline">
                platform.openai.com
              </a>
            </span>
          </div>

          {!loadingSettings && settings?.openai_api_key && (
            <div className="flex items-center gap-2 px-4 py-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>مفتاح OpenAI API مضبوط ✓</span>
            </div>
          )}

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-400 block">المفتاح الجديد</label>
            <div className="relative flex items-center">
              <input
                type={showKey ? "text" : "password"}
                dir="ltr"
                placeholder="sk-proj-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 rounded-xl px-4 py-3 pr-12 text-slate-100 placeholder-slate-600 text-sm font-mono outline-none transition-all duration-200"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute left-3 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[11px] text-slate-500">اترك الحقل فارغاً إذا كنت لا تريد تغيير المفتاح الحالي</p>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={saveMutation.isPending || !openaiKey.trim()}
              className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:pointer-events-none text-white font-bold py-2.5 px-6 rounded-xl flex items-center gap-2 text-sm transition-all"
            >
              {saveMutation.isPending ? (
                <><Loader2 className="w-4 h-4 animate-spin" /><span>جاري الحفظ...</span></>
              ) : (
                <><Save className="w-4 h-4" /><span>حفظ المفتاح</span></>
              )}
            </button>
          </div>
        </div>
      </form>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-3">
        <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
          <Bot className="w-5 h-5 text-violet-400" />
          معلومات المنصة
        </h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            { label: "اسم المنصة", value: "رسن (Rasan)" },
            { label: "الإصدار", value: "1.0.0" },
            { label: "نموذج الذكاء الاصطناعي", value: "GPT-4o mini" },
            { label: "نظام RAG", value: "OpenAI Embeddings + pgvector" },
          ].map((item) => (
            <div key={item.label} className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
              <p className="text-[10px] text-slate-500 mb-0.5">{item.label}</p>
              <p className="text-slate-300 font-medium text-xs">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
