import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plug,
  Copy,
  Check,
  Send,
  Globe,
  Code2,
  Bot,
  Info,
  Save,
  Loader2,
  CheckCircle,
  AlertCircle,
  Key,
  ExternalLink
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className={`flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg transition-all duration-200 ${
        copied
          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
          : "bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 border border-slate-700"
      }`}
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "تم النسخ!" : "نسخ"}
    </button>
  );
}

export default function IntegrationPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const tenantId = user?.tenant_id;

  const [tgToken, setTgToken] = useState("");
  const [tgSuccess, setTgSuccess] = useState("");
  const [tgError, setTgError] = useState("");

  const { data: tenant, isLoading } = useQuery<any>({
    queryKey: ["tenantIntegration", tenantId],
    queryFn: async () => {
      if (!tenantId) throw new Error("no tenant");
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}`);
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    enabled: !!tenantId,
  });

  const tgMutation = useMutation({
    mutationFn: async (token: string) => {
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_bot_token: token }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل في حفظ توكن تيليجرام");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenantIntegration", tenantId] });
      setTgToken("");
      setTgSuccess("تم ربط بوت تيليجرام بنجاح!");
      setTimeout(() => setTgSuccess(""), 4000);
    },
    onError: (err: Error) => setTgError(err.message),
  });

  const embedCode = `<script>
  window.RasanConfig = {
    botId: "${tenantId || "YOUR_BOT_ID"}",
    primaryColor: "#10b981",
    lang: "ar"
  };
</script>
<script async src="https://cdn.rasan.ai/widget.js"></script>`;

  const webhookUrl = `${window.location.origin}${BASE}/api/v1/telegram/${tenantId}/webhook`;

  const handleSaveTelegram = (e: React.FormEvent) => {
    e.preventDefault();
    setTgError("");
    const token = tgToken.trim();
    if (!token) { setTgError("يرجى إدخال توكن البوت."); return; }
    tgMutation.mutate(token);
  };

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
        <span className="text-sm text-slate-400">جاري التحميل...</span>
      </div>
    );
  }

  const hasTgToken = !!(tenant?.config?.telegram_bot_token);

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          <Plug className="w-6 h-6 text-emerald-500" />
          <span>التكامل والنشر</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          انشر الشات بوت على موقعك الإلكتروني أو ربطه بـ Telegram — كل ذلك في دقائق.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex items-start gap-4">
          <div className="w-10 h-10 bg-blue-500/10 rounded-xl flex items-center justify-center shrink-0">
            <Globe className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-200">تضمين في موقعك</p>
            <p className="text-xs text-slate-500 mt-1">أضف سطرين من الكود وسيظهر البوت كأداة دردشة منبثقة.</p>
          </div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex items-start gap-4">
          <div className="w-10 h-10 bg-sky-500/10 rounded-xl flex items-center justify-center shrink-0">
            <Send className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-200">ربط تيليجرام</p>
            <p className="text-xs text-slate-500 mt-1">أنشئ بوت على Telegram واربطه بمنصة رسن في ثوانٍ.</p>
          </div>
        </div>
      </div>

      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xl">
        <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
          <Code2 className="w-5 h-5 text-blue-400" />
          <span>كود تضمين الويدجت في موقعك</span>
        </h2>

        <div className="p-3 bg-blue-500/5 border border-blue-500/20 rounded-2xl flex items-start gap-3">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-400 leading-relaxed">
            انسخ الكود التالي والصقه قبل نهاية وسم <code className="text-blue-300 font-mono bg-slate-800 px-1 rounded">&lt;/body&gt;</code> في كل صفحة تريد ظهور الشات بوت فيها.
          </p>
        </div>

        <div className="relative">
          <pre className="bg-slate-950 border border-slate-800 rounded-2xl p-5 text-xs text-emerald-300 font-mono overflow-x-auto leading-relaxed whitespace-pre" dir="ltr">
            {embedCode}
          </pre>
          <div className="absolute top-3 left-3">
            <CopyButton text={embedCode} />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
          {[
            { step: "1", text: "انسخ الكود" },
            { step: "2", text: "الصقه في موقعك قبل </body>" },
            { step: "3", text: "الشات بوت يظهر فوراً!" },
          ].map((s) => (
            <div key={s.step} className="flex items-center gap-3 p-3 bg-slate-950/40 rounded-xl border border-slate-800/60">
              <div className="w-7 h-7 bg-emerald-500/10 rounded-full flex items-center justify-center shrink-0">
                <span className="text-xs font-bold text-emerald-400">{s.step}</span>
              </div>
              <span className="text-xs text-slate-400">{s.text}</span>
            </div>
          ))}
        </div>
      </div>

      <form onSubmit={handleSaveTelegram}>
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xl">
          <h2 className="text-base font-bold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
            <Send className="w-5 h-5 text-sky-400" />
            <span>ربط بوت Telegram</span>
          </h2>

          {hasTgToken && (
            <div className="flex items-center gap-2.5 px-4 py-3 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>بوت تيليجرام مربوط ومفعّل ✓</span>
            </div>
          )}

          {tgSuccess && (
            <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-center gap-2.5 text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>{tgSuccess}</span>
            </div>
          )}
          {tgError && (
            <div className="p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-center gap-2.5 text-rose-400 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{tgError}</span>
            </div>
          )}

          <div className="p-4 bg-slate-950/40 border border-slate-800 rounded-2xl space-y-2">
            <p className="text-xs font-bold text-slate-400">كيفية إنشاء بوت تيليجرام:</p>
            <ol className="text-xs text-slate-500 space-y-1.5 list-decimal list-inside leading-relaxed">
              <li>افتح تيليجرام وابحث عن <span className="text-sky-400 font-mono">@BotFather</span></li>
              <li>أرسل الأمر <span className="font-mono text-slate-300">/newbot</span> واتبع التعليمات</li>
              <li>انسخ الـ <span className="font-mono text-slate-300">Token</span> الذي يُعطيك إياه والصقه هنا</li>
            </ol>
            <a
              href="https://t.me/BotFather"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 mt-1 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              افتح @BotFather الآن
            </a>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5" />
              <span>Telegram Bot Token</span>
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                dir="ltr"
                placeholder="1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                value={tgToken}
                onChange={(e) => setTgToken(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-600 text-xs font-mono outline-none transition-all duration-200"
              />
              <button
                type="submit"
                disabled={tgMutation.isPending}
                className="bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-bold px-5 rounded-xl flex items-center gap-2 shadow-md transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none shrink-0 text-sm"
              >
                {tgMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>{tgMutation.isPending ? "جاري الحفظ..." : "ربط البوت"}</span>
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5" />
              <span>رابط الـ Webhook (لا تحتاج لضبطه يدوياً)</span>
            </label>
            <div className="relative">
              <input
                type="text"
                dir="ltr"
                readOnly
                value={webhookUrl}
                className="w-full bg-slate-950/50 border border-slate-800 rounded-xl px-4 py-3 text-slate-500 text-xs font-mono outline-none select-all cursor-text"
              />
              <div className="absolute top-1/2 left-3 -translate-y-1/2">
                <CopyButton text={webhookUrl} />
              </div>
            </div>
            <p className="text-[11px] text-slate-600">يُضبط هذا الرابط تلقائياً عند حفظ التوكن.</p>
          </div>
        </div>
      </form>

      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 space-y-4">
        <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
          <Globe className="w-5 h-5 text-emerald-500" />
          <span>معرّف الشات بوت (Bot ID)</span>
        </h2>
        <div className="flex items-center gap-3">
          <code className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm font-mono text-emerald-400 select-all" dir="ltr">
            {tenantId || "—"}
          </code>
          {tenantId && <CopyButton text={tenantId} />}
        </div>
        <p className="text-xs text-slate-500">
          هذا المعرّف الفريد لشركتك في المنصة — يستخدم في كود التضمين وإعدادات API.
        </p>
      </div>
    </div>
  );
}
