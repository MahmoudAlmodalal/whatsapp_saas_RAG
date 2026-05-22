"use client";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  Bot, 
  Sliders, 
  MessageSquare, 
  Plus, 
  X, 
  Save, 
  Loader2, 
  CheckCircle, 
  AlertCircle, 
  Globe, 
  Volume2,
  Info,
  HelpCircle
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
  whatsapp_number: string | null;
  subscription_tier: string;
  config: Partial<TenantConfig>;
  is_active: boolean;
}

export default function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const tenantId = user?.tenant_id;

  // Local Form State
  const [personaName, setPersonaName] = useState("");
  const [language, setLanguage] = useState("ar");
  const [tone, setTone] = useState("friendly");
  const [confidence, setConfidence] = useState(0.7);
  const [maxTurns, setMaxTurns] = useState(10);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState("");
  
  // Feedback Messages
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Fetch Tenant Settings
  const { data: tenant, isLoading } = useQuery<TenantData>({
    queryKey: ["tenantSettings", tenantId],
    queryFn: async () => {
      if (!tenantId) throw new Error("لم يتم العثور على معرف الشريك");
      const res = await fetch(`/api/v1/tenants/${tenantId}`);
      if (!res.ok) throw new Error("فشل في تحميل إعدادات الشريك");
      return res.json();
    },
    enabled: !!tenantId,
  });

  // Sync state when data is loaded
  useEffect(() => {
    if (tenant?.config) {
      const cfg = tenant.config;
      setPersonaName(cfg.ai_persona_name || "مساعد خدمة العملاء الذكي");
      setLanguage(cfg.language || "ar");
      setTone(cfg.tone || "friendly");
      setConfidence(cfg.confidence_threshold !== undefined ? cfg.confidence_threshold : 0.7);
      setMaxTurns(cfg.max_context_turns !== undefined ? cfg.max_context_turns : 10);
      setKeywords(cfg.handoff_keywords || ["وكيل", "موظف", "بشري", "مساعدة"]);
    }
  }, [tenant]);

  // Update Settings Mutation
  const saveMutation = useMutation({
    mutationFn: async (updatedConfig: TenantConfig) => {
      setErrorMsg("");
      setSuccessMsg("");
      const res = await fetch(`/api/v1/tenants/${tenantId}/config`, {
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
      setSuccessMsg("تم حفظ الإعدادات وتحديث سلوك المجيب الآلي بنجاح.");
      // Clear message after 4s
      setTimeout(() => setSuccessMsg(""), 4000);
    },
    onError: (err: Error) => {
      setErrorMsg(err.message || "فشل الاتصال بالخادم لحفظ الإعدادات");
    }
  });

  // Keywords management helpers
  const handleAddKeyword = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanWord = newKeyword.trim().toLowerCase();
    if (!cleanWord) return;
    if (keywords.includes(cleanWord)) {
      setNewKeyword("");
      return;
    }
    setKeywords([...keywords, cleanWord]);
    setNewKeyword("");
  };

  const handleRemoveKeyword = (wordToRemove: string) => {
    setKeywords(keywords.filter(w => w !== wordToRemove));
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!personaName.trim()) {
      setErrorMsg("يرجى ملء اسم شخصية المجيب الآلي.");
      return;
    }
    if (maxTurns < 1 || maxTurns > 30) {
      setErrorMsg("عدد الرسائل المرجعية في السياق يجب أن يكون بين 1 و 30.");
      return;
    }

    const payload: TenantConfig = {
      ai_persona_name: personaName.trim(),
      language,
      tone,
      handoff_keywords: keywords,
      confidence_threshold: parseFloat(confidence.toFixed(2)),
      max_context_turns: maxTurns,
    };

    saveMutation.mutate(payload);
  };

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
        <span className="text-sm text-slate-400 font-medium">جاري تحميل إعدادات الروبوت...</span>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          <Sliders className="w-6 h-6 text-emerald-500" />
          <span>إعدادات المجيب الآلي</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          قم بتعديل وتخصيص طريقة تفاعل الذكاء الاصطناعي مع عملائك وخصائص شخصيته ومحددات النقل البشري.
        </p>
      </div>

      {/* Alert Banners */}
      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-start gap-3 text-emerald-400 text-sm animate-fade-in shadow-lg shadow-emerald-500/[0.02]">
          <CheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3 text-rose-400 text-sm animate-fade-in shadow-lg shadow-rose-500/[0.02]">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Main Settings Form Card */}
      <form onSubmit={handleSave} className="space-y-6">
        
        {/* Row 1: AI Persona & Details */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Bot className="w-5 h-5 text-emerald-500" />
            <span>الهوية الشخصية للذكاء الاصطناعي</span>
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Persona Name */}
            <div className="space-y-2">
              <label htmlFor="persona-name" className="text-xs font-semibold text-slate-400 block mr-1">
                اسم شخصية الذكاء الاصطناعي
              </label>
              <input
                id="persona-name"
                type="text"
                placeholder="مثال: مساعد سارة الذكي"
                value={personaName}
                onChange={(e) => setPersonaName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
              />
              <p className="text-[10px] text-slate-500 mr-1">هذا الاسم يمثل الهوية التي سيعرف بها المجيب الآلي نفسه لعملائك.</p>
            </div>

            {/* Language */}
            <div className="space-y-2">
              <label htmlFor="language-select" className="text-xs font-semibold text-slate-400 block mr-1 flex items-center gap-1">
                <Globe className="w-3.5 h-3.5 text-slate-500" />
                <span>لغة التحدث الأساسية</span>
              </label>
              <select
                id="language-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-4 py-3 text-slate-100 text-sm outline-none transition-all duration-200 appearance-none"
              >
                <option value="ar">العربية (Arabic-First)</option>
                <option value="en">الإنجليزية (English)</option>
                <option value="both">مزدوج (العربية والإنجليزية)</option>
              </select>
              <p className="text-[10px] text-slate-500 mr-1">تحديد لغة صياغة الأجوبة ونبرة الترجمات.</p>
            </div>
            
            {/* Tone selection */}
            <div className="space-y-2 md:col-span-2">
              <label className="text-xs font-semibold text-slate-400 block mr-1 flex items-center gap-1">
                <Volume2 className="w-3.5 h-3.5 text-slate-500" />
                <span>أسلوب الحوار ونبرة الصوت (Tone)</span>
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { id: "friendly", title: "ودود ولطيف", desc: "أجوبة دافئة وعبارات ترحيبية" },
                  { id: "professional", title: "مهني ومحترف", desc: "أسلوب عملي وواضح ودقيق" },
                  { id: "formal", title: "رسمي وجاد", desc: "لغة فصحى رسمية للغاية" },
                  { id: "concise", title: "مباشر وموجز", desc: "أجوبة قصيرة ومختصرة للسرعة" }
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTone(t.id)}
                    className={`p-4 rounded-2xl border text-right transition-all duration-250 flex flex-col justify-between h-24 ${
                      tone === t.id
                        ? "bg-emerald-500/10 border-emerald-500 text-emerald-400"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:bg-slate-950/80"
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

        {/* Row 2: Precision & Context parameters */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Sliders className="w-5 h-5 text-emerald-500" />
            <span>معايير التحكم والحساسية</span>
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Confidence Threshold */}
            <div className="space-y-4">
              <div className="flex items-center justify-between mr-1">
                <label className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                  حد الثقة للإجابة الآلية
                  <span className="group relative cursor-pointer text-slate-500 hover:text-slate-400">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span className="absolute bottom-full right-1/2 translate-x-1/2 mb-2 w-48 bg-slate-950 border border-slate-800 text-slate-400 text-[10px] p-2.5 rounded-xl shadow-xl pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-30 leading-normal">
                      عندما تقل ثقة النموذج في الإجابة المستخرجة من مستنداتك عن هذه النسبة، يمتنع عن الرد ويحيل الجلسة لموظف.
                    </span>
                  </span>
                </label>
                <span className="font-mono text-xs font-extrabold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  {Math.round(confidence * 100)}%
                </span>
              </div>
              
              <div className="space-y-2">
                <input
                  type="range"
                  min="0.30"
                  max="0.95"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-emerald-500 focus:outline-none"
                />
                <div className="flex items-center justify-between text-[9px] text-slate-600 font-mono px-1">
                  <span>منخفض (30%) - سريع الرد</span>
                  <span>مرتفع (95%) - شديد التحقق</span>
                </div>
              </div>
            </div>

            {/* Max Context Turns */}
            <div className="space-y-4">
              <div className="flex items-center justify-between mr-1">
                <label className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                  سياق الحوار المسترجع (Context Turns)
                  <span className="group relative cursor-pointer text-slate-500 hover:text-slate-400">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span className="absolute bottom-full right-1/2 translate-x-1/2 mb-2 w-48 bg-slate-950 border border-slate-800 text-slate-400 text-[10px] p-2.5 rounded-xl shadow-xl pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-30 leading-normal">
                      عدد الرسائل السابقة المتبادلة المرفقة مع الطلب، لتذكير الذكاء الاصطناعي بما قاله العميل قبل قليل.
                    </span>
                  </span>
                </label>
                <span className="font-mono text-xs font-extrabold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/20">
                  {maxTurns} رسائل
                </span>
              </div>

              <div className="space-y-2">
                <input
                  type="range"
                  min="2"
                  max="20"
                  step="1"
                  value={maxTurns}
                  onChange={(e) => setMaxTurns(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-emerald-500 focus:outline-none"
                />
                <div className="flex items-center justify-between text-[9px] text-slate-600 font-mono px-1">
                  <span>2 رسائل (ذاكرة ضعيفة)</span>
                  <span>20 رسائل (ذاكرة عميقة)</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Row 3: Handoff Keywords */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-emerald-500" />
            <span>كلمات مفاتيح التحويل للموظفين (Handoff Keywords)</span>
          </h2>
          
          <div className="space-y-4">
            <div className="p-4 bg-slate-950/40 border border-slate-800 rounded-2xl flex items-start gap-3">
              <Info className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <p className="text-xs text-slate-400 leading-normal">
                إذا أرسل العميل أي كلمة تطابق الكلمات المعرّفة بالأسفل في رسالته، سيقوم النظام تلقائياً بإيقاف المجيب الآلي ونقل الدردشة لقائمة انتظار خدمة العملاء.
              </p>
            </div>

            {/* Keyword Input Form */}
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="أضف كلمة جديدة (مثلاً: شكوى، أسعار، استرجاع)..."
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddKeyword(e);
                  }
                }}
                className="flex-1 bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
              />
              <button
                type="button"
                onClick={handleAddKeyword}
                className="bg-slate-800 hover:bg-slate-700 text-emerald-400 font-bold px-4 rounded-xl border border-slate-700 hover:border-emerald-500/30 transition-all duration-200 flex items-center gap-1 shrink-0"
              >
                <Plus className="w-4 h-4" />
                <span>إضافة</span>
              </button>
            </div>

            {/* Keywords list */}
            <div className="flex flex-wrap gap-2.5 pt-2">
              {keywords.length === 0 ? (
                <span className="text-xs text-slate-600 italic">لا توجد كلمات مفتاحية معرّفة حالياً. سيتم التحويل بطلب العميل فقط.</span>
              ) : (
                keywords.map((word) => (
                  <span
                    key={word}
                    className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl font-medium animate-fade-in group hover:bg-rose-500/5 hover:text-rose-400 hover:border-rose-500/20 transition-all duration-150"
                  >
                    <span>{word}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveKeyword(word)}
                      className="text-slate-500 group-hover:text-rose-400 hover:scale-110 transition-all"
                      title={`حذف "${word}"`}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Form Submission Actions */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="w-full sm:w-auto bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold py-3.5 px-8 rounded-2xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/10 hover:shadow-emerald-500/20 transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none"
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>جاري حفظ التغييرات...</span>
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                <span>حفظ الإعدادات</span>
              </>
            )}
          </button>
        </div>

      </form>
    </div>
  );
}
