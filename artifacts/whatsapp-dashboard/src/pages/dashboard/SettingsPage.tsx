import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Settings, Bot, Globe, Volume2, Save, CheckCircle, AlertCircle, Loader2, Send, MessageSquare } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface BotSettings {
  company_name: string;
  persona_name: string;
  tone: string;
  language_preference: string;
  system_prompt_extra: string;
  telegram_token: string;
}

interface ChatMsg { role: "user" | "assistant"; content: string; }

export default function SettingsPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState<BotSettings | null>(null);
  const [saved, setSaved] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const { data, isLoading } = useQuery<BotSettings>({
    queryKey: ["bot-settings"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/settings?company_id=default`, { credentials: "include" });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
  });

  useEffect(() => { if (data && !form) setForm(data); }, [data]);

  const saveMut = useMutation({
    mutationFn: async (s: BotSettings) => {
      const res = await fetch(`${BASE}/api/v1/settings?company_id=default`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(s),
      });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      qc.invalidateQueries({ queryKey: ["bot-settings"] });
    },
  });

  async function sendChat() {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatHistory((h) => [...h, { role: "user", content: msg }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${BASE}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: msg, session_id: `settings_test_${Date.now()}`, company_id: "default" }),
      });
      const d = await res.json();
      setChatHistory((h) => [...h, { role: "assistant", content: d.answer ?? "خطأ في الاتصال" }]);
    } catch {
      setChatHistory((h) => [...h, { role: "assistant", content: "تعذر الاتصال بالخادم" }]);
    } finally {
      setChatLoading(false);
    }
  }

  if (isLoading || !form) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="w-6 h-6 text-emerald-500 animate-spin" /></div>;
  }

  const field = (key: keyof BotSettings) => ({
    value: form[key] as string,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((p) => p ? { ...p, [key]: e.target.value } : p),
  });

  return (
    <div className="p-8 space-y-8" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-100">إعدادات البوت</h1>
        <p className="text-slate-400 text-sm mt-1">خصّص شخصية نصيح ونبرته وإعدادات القناة</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
            <div className="flex items-center gap-2 mb-1">
              <Bot className="w-5 h-5 text-emerald-400" />
              <h2 className="font-bold text-slate-100">الشخصية</h2>
            </div>
            <div className="space-y-1">
              <label className="text-slate-400 text-xs font-medium">اسم الشركة</label>
              <input {...field("company_name")} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
            </div>
            <div className="space-y-1">
              <label className="text-slate-400 text-xs font-medium">اسم البوت (اسم المساعد الذكي)</label>
              <input {...field("persona_name")} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
            <div className="flex items-center gap-2 mb-1">
              <Volume2 className="w-5 h-5 text-violet-400" />
              <h2 className="font-bold text-slate-100">النبرة واللغة</h2>
            </div>
            <div className="space-y-1">
              <label className="text-slate-400 text-xs font-medium">نبرة الردود</label>
              <select {...field("tone")} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:border-emerald-500">
                <option value="professional">محترف (Professional)</option>
                <option value="friendly">ودود (Friendly)</option>
                <option value="formal">رسمي (Formal)</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-slate-400 text-xs font-medium">تفضيل اللغة</label>
              <select {...field("language_preference")} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:border-emerald-500">
                <option value="auto">تلقائي (Auto-detect)</option>
                <option value="ar">عربي دائماً</option>
                <option value="en">English only</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-slate-400 text-xs font-medium">تعليمات إضافية للبوت (اختياري)</label>
              <textarea {...field("system_prompt_extra")} rows={3} placeholder="مثال: دائماً أنهِ ردودك بـ 'شكراً لتواصلك معنا'" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 resize-none" />
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 mb-1">
              <Send className="w-5 h-5 text-blue-400" />
              <h2 className="font-bold text-slate-100">Telegram</h2>
            </div>
            <div className="space-y-1">
              <label className="text-slate-400 text-xs font-medium">Bot Token (من @BotFather)</label>
              <input {...field("telegram_token")} placeholder="123456:ABC..." className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 font-mono" />
            </div>
          </div>

          <button
            onClick={() => form && saveMut.mutate(form)}
            disabled={saveMut.isPending}
            className="w-full flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-3 rounded-xl transition-colors disabled:opacity-50">
            {saveMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saved ? "تم الحفظ!" : "حفظ الإعدادات"}
          </button>
          {saved && <p className="text-emerald-400 text-sm text-center">✓ تم حفظ الإعدادات بنجاح</p>}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col" style={{ height: "600px" }}>
          <div className="p-4 border-b border-slate-800 flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-200 font-medium text-sm">اختبر البوت الآن</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chatHistory.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <p className="text-slate-600 text-sm">اكتب سؤالاً لتجربة البوت...</p>
              </div>
            )}
            {chatHistory.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                  m.role === "user" ? "bg-emerald-500/20 text-emerald-100" : "bg-slate-800 text-slate-200"}`}>
                  {m.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-slate-800 rounded-2xl px-4 py-3">
                  <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                </div>
              </div>
            )}
          </div>
          <div className="p-4 border-t border-slate-800 flex gap-2">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendChat()}
              placeholder="اسأل نصيح..."
              className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
            <button onClick={sendChat} disabled={chatLoading}
              className="w-10 h-10 bg-emerald-500 hover:bg-emerald-400 rounded-xl flex items-center justify-center transition-colors disabled:opacity-50">
              <Send className="w-4 h-4 text-slate-950" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
