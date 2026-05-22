import React, { useState, useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Sliders,
  Plus,
  X,
  Save,
  Loader2,
  CheckCircle,
  AlertCircle,
  Globe,
  Volume2,
  Info,
} from "lucide-react";

interface TenantConfig {
  ai_persona_name: string;
  language: string;
  tone: string;
  handoff_keywords: string[];
  confidence_threshold: number;
  max_context_turns: number;
}

interface TenantData {
  id: string;
  name: string;
  subscription_tier: string;
  config: Partial<TenantConfig>;
  is_active: boolean;
}

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const tenantId = user?.tenant_id;

  const [personaName, setPersonaName] = useState("");
  const [language, setLanguage] = useState("ar");
  const [tone, setTone] = useState("friendly");
  const [confidence, setConfidence] = useState(0.7);
  const [maxTurns, setMaxTurns] = useState(10);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const { data: tenant, isLoading } = useQuery<TenantData>({
    queryKey: ["tenantSettings", tenantId],
    queryFn: async () => {
      if (!tenantId) throw new Error("لم يتم العثور على معرف الشريك");
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}`);
      if (!res.ok) throw new Error("فشل في تحميل إعدادات الشريك");
      return res.json();
    },
    enabled: !!tenantId,
  });

  useEffect(() => {
    if (tenant) {
      const cfg = tenant.config;
      setPersonaName(cfg.ai_persona_name || "مساعد رسن الذكي");
      setLanguage(cfg.language || "ar");
      setTone(cfg.tone || "friendly");
      setConfidence(cfg.confidence_threshold !== undefined ? cfg.confidence_threshold : 0.7);
      setMaxTurns(cfg.max_context_turns !== undefined ? cfg.max_context_turns : 10);
      setKeywords(cfg.handoff_keywords || ["وكيل", "موظف", "بشري", "مساعدة"]);
    }
  }, [tenant]);

  const saveMutation = useMutation({
    mutationFn: async (updatedConfig: TenantConfig) => {
      setErrorMsg("");
      setSuccessMsg("");
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedConfig),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "حدث خطأ أثناء حفظ الإعدادات");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenantSettings", tenantId] });
      setSuccessMsg("تم حفظ الإعدادات بنجاح وتحديث سلوك الشات بوت.");
      setTimeout(() => setSuccessMsg(""), 4000);
    },
    onError: (err: Error) => setErrorMsg(err.message || "فشل الاتصال بالخادم لحفظ الإعدادات"),
  });

  const handleAddKeyword = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanWord = newKeyword.trim().toLowerCase();
    if (!cleanWord) return;
    if (keywords.includes(cleanWord)) { setNewKeyword(""); return; }
    setKeywords([...keywords, cleanWord]);
    setNewKeyword("");
  };

  const handleRemoveKeyword = (word: string) => setKeywords(keywords.filter(w => w !== word));

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!personaName.trim()) { setErrorMsg("يرجى ملء اسم شخصية الشات بوت."); return; }
    if (maxTurns < 1 || maxTurns > 30) { setErrorMsg("عدد الرسائل يجب أن يكون بين 1 و 30."); return; }
    saveMutation.mutate({
      ai_persona_name: personaName.trim(),
      language,
      tone,
      handoff_keywords: keywords,
      confidence_threshold: parseFloat(confidence.toFixed(2)),
      max_context_turns: maxTurns,
    });
  };

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
        <span className="text-sm text-slate-400 font-medium">جاري تحميل إعدادات الشات بوت...</span>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          <Sliders className="w-6 h-6 text-emerald-500" />
          <span>إعدادات الشات بوت</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          خصّص شخصية الشات بوت وطريقة تفاعله مع عملاء شركتك.
        </p>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-start gap-3 text-emerald-400 text-sm animate-fade-in">
          <CheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3 text-rose-400 text-sm animate-fade-in">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Bot className="w-5 h-5 text-emerald-500" />
            <span>هوية الشات بوت</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label htmlFor="persona-name" className="text-xs font-semibold text-slate-400 block mr-1">
                اسم الشات بوت
              </label>
              <input
                id="persona-name"
                type="text"
                placeholder="مثال: مساعد رسن الذكي"
                value={personaName}
                onChange={(e) => setPersonaName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="language-select" className="text-xs font-semibold text-slate-400 mr-1 flex items-center gap-1">
                <Globe className="w-3.5 h-3.5 text-slate-500" />
                <span>لغة الرد الأساسية</span>
              </label>
              <select
                id="language-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-4 py-3 text-slate-100 text-sm outline-none transition-all duration-200 appearance-none"
              >
                <option value="ar">العربية</option>
                <option value="en">الإنجليزية</option>
                <option value="both">ثنائي (عربي + إنجليزي)</option>
              </select>
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-xs font-semibold text-slate-400 mr-1 flex items-center gap-1">
                <Volume2 className="w-3.5 h-3.5 text-slate-500" />
                <span>أسلوب الرد ونبرة الحوار</span>
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { id: "friendly",     title: "ودود ولطيف",    desc: "أجوبة دافئة وعبارات ترحيبية" },
                  { id: "professional", title: "مهني ومحترف",   desc: "أسلوب عملي وواضح ودقيق" },
                  { id: "formal",       title: "رسمي وجاد",     desc: "لغة فصحى رسمية للغاية" },
                  { id: "concise",      title: "مباشر وموجز",   desc: "أجوبة قصيرة ومختصرة" },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTone(t.id)}
                    className={`p-4 rounded-2xl border text-right transition-all duration-200 flex flex-col justify-between h-24 ${
                      tone === t.id
                        ? "bg-emerald-500/10 border-emerald-500 text-emerald-400"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <span className="font-bold text-xs block">{t.title}</span>
                    <span className="text-[9px] leading-tight text-slate-500 block">{t.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Sliders className="w-5 h-5 text-emerald-500" />
            <span>إعدادات متقدمة</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-400 flex items-center gap-1">
                  عتبة الثقة (Confidence Threshold)
                </label>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-lg">
                  {(confidence * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min={0.1}
                max={1}
                step={0.05}
                value={confidence}
                onChange={(e) => setConfidence(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <p className="text-[11px] text-slate-500">
                إذا كانت ثقة البوت بالإجابة أقل من هذه النسبة، يُحوّل المحادثة لوكيل بشري.
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-400 block">
                عدد الرسائل السابقة في السياق
              </label>
              <input
                type="number"
                min={1}
                max={30}
                value={maxTurns}
                onChange={(e) => setMaxTurns(parseInt(e.target.value) || 10)}
                className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-4 py-3 text-slate-100 text-sm outline-none transition-all duration-200"
              />
              <p className="text-[11px] text-slate-500">عدد رسائل السياق التي يتذكرها البوت (1–30).</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Info className="w-5 h-5 text-emerald-500" />
            <span>كلمات تحويل المحادثة لوكيل بشري</span>
          </h2>
          <p className="text-xs text-slate-500">
            إذا أرسل العميل إحدى هذه الكلمات، يُحوّل البوت المحادثة تلقائياً إلى وكيل بشري.
          </p>
          <div className="flex flex-wrap gap-2">
            {keywords.map((word) => (
              <span
                key={word}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 text-slate-300 text-xs rounded-xl font-mono border border-slate-700"
              >
                {word}
                <button
                  type="button"
                  onClick={() => handleRemoveKeyword(word)}
                  className="text-slate-500 hover:text-rose-400 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            {keywords.length === 0 && (
              <span className="text-xs text-slate-600">لا توجد كلمات بعد</span>
            )}
          </div>
          <form onSubmit={handleAddKeyword} className="flex gap-2">
            <input
              type="text"
              placeholder="أضف كلمة جديدة..."
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
            />
            <button
              type="submit"
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-4 rounded-xl flex items-center gap-1.5 border border-slate-700 transition-all text-sm"
            >
              <Plus className="w-4 h-4" />
              إضافة
            </button>
          </form>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold py-3.5 px-8 rounded-xl flex items-center gap-2 shadow-lg shadow-emerald-500/10 hover:shadow-emerald-500/20 transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none text-sm"
          >
            {saveMutation.isPending ? (
              <><Loader2 className="w-5 h-5 animate-spin" /><span>جاري الحفظ...</span></>
            ) : (
              <><Save className="w-5 h-5" /><span>حفظ الإعدادات</span></>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
