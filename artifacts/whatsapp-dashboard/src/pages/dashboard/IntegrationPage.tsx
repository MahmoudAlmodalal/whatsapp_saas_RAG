import React, { useState } from "react";
import { Copy, Check, Code2, MessageSquare, Send, Globe, Zap } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors">
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "تم النسخ" : "نسخ"}
    </button>
  );
}

export default function IntegrationPage() {
  const chatEndpoint = `${window.location.origin}${BASE}/api/v1/chat`;
  const uploadEndpoint = `${window.location.origin}${BASE}/api/v1/upload`;
  const wsEndpoint = `${window.location.origin.replace("https", "wss").replace("http", "ws")}${BASE}/api/v1/ws/SESSION_ID`;

  const widgetCode = `<script>
  (function() {
    var w = document.createElement('iframe');
    w.src = '${window.location.origin}${BASE}/widget';
    w.style.cssText = 'position:fixed;bottom:20px;left:20px;width:380px;height:550px;border:none;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.3);z-index:9999';
    document.body.appendChild(w);
  })();
</script>`;

  const curlExample = `curl -X POST ${chatEndpoint} \\
  -H "Content-Type: application/json" \\
  -d '{"message": "ما هي خدماتكم؟", "session_id": "user123", "company_id": "default"}'`;

  return (
    <div className="p-8 space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-100">التكامل والنشر</h1>
        <p className="text-slate-400 text-sm mt-1">اربط نصيح بموقعك أو Telegram أو WhatsApp</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {[
          { icon: Globe, label: "Web Widget", color: "text-emerald-400", bg: "bg-emerald-500/10", desc: "ودجت قابل للتضمين في أي موقع" },
          { icon: Send, label: "Telegram Bot", color: "text-blue-400", bg: "bg-blue-500/10", desc: "بوت Telegram مع webhook" },
          { icon: MessageSquare, label: "WhatsApp (Twilio)", color: "text-green-400", bg: "bg-green-500/10", desc: "WhatsApp Business عبر Twilio" },
        ].map((c) => (
          <div key={c.label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex items-center gap-4">
            <div className={`w-12 h-12 ${c.bg} rounded-xl flex items-center justify-center shrink-0`}>
              <c.icon className={`w-6 h-6 ${c.color}`} />
            </div>
            <div>
              <p className="text-slate-200 font-semibold text-sm">{c.label}</p>
              <p className="text-slate-500 text-xs mt-0.5">{c.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Code2 className="w-5 h-5 text-emerald-400" />
              <h2 className="font-bold text-slate-100">Web Widget — كود التضمين</h2>
            </div>
            <CopyButton text={widgetCode} />
          </div>
        </div>
        <div className="p-5">
          <pre className="text-emerald-300 text-xs leading-relaxed bg-slate-950/50 rounded-xl p-4 overflow-x-auto">{widgetCode}</pre>
          <p className="text-slate-500 text-xs mt-3">الصق هذا الكود قبل إغلاق وسم &lt;/body&gt; في موقعك</p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            <h2 className="font-bold text-slate-100">API Endpoints</h2>
          </div>
        </div>
        <div className="divide-y divide-slate-800">
          {[
            { method: "POST", path: "/api/v1/chat", desc: "إرسال رسالة والحصول على رد AI" },
            { method: "POST", path: "/api/v1/upload", desc: "رفع ملف لقاعدة المعرفة" },
            { method: "GET", path: "/api/v1/analytics", desc: "إحصائيات الاستخدام" },
            { method: "POST", path: "/api/v1/handoff", desc: "إنشاء تحويل لموظف بشري" },
            { method: "POST", path: "/api/v1/learn", desc: "إضافة سؤال/جواب للمعرفة" },
            { method: "WS", path: "/api/v1/ws/{session_id}", desc: "WebSocket للدردشة المباشرة" },
          ].map((ep) => (
            <div key={ep.path} className="flex items-center gap-4 px-5 py-3.5">
              <span className={`text-xs font-bold px-2 py-1 rounded font-mono shrink-0 ${
                ep.method === "GET" ? "bg-green-500/10 text-green-400" :
                ep.method === "WS" ? "bg-purple-500/10 text-purple-400" :
                "bg-blue-500/10 text-blue-400"}`}>
                {ep.method}
              </span>
              <code className="text-slate-300 text-xs font-mono flex-1">{ep.path}</code>
              <p className="text-slate-500 text-xs">{ep.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Code2 className="w-5 h-5 text-slate-400" />
              <h2 className="font-bold text-slate-100">مثال — cURL</h2>
            </div>
            <CopyButton text={curlExample} />
          </div>
        </div>
        <div className="p-5">
          <pre className="text-slate-300 text-xs leading-relaxed bg-slate-950/50 rounded-xl p-4 overflow-x-auto">{curlExample}</pre>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Send className="w-5 h-5 text-blue-400" />
          <h2 className="font-bold text-slate-100">إعداد Telegram Webhook</h2>
        </div>
        <p className="text-slate-400 text-sm">بعد إضافة Bot Token في الإعدادات، شغّل الأمر التالي لتسجيل الـ webhook:</p>
        <div className="relative">
          <pre className="text-slate-300 text-xs bg-slate-950/50 rounded-xl p-4 overflow-x-auto">{`curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \\
  -d "url=${window.location.origin}${BASE}/api/v1/telegram/webhook"`}</pre>
        </div>
        <p className="text-slate-500 text-xs">استبدل &lt;TOKEN&gt; بتوكن البوت الخاص بك من @BotFather</p>
      </div>
    </div>
  );
}
