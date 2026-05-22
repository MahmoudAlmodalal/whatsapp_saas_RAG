import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Lock, Mail, Loader2, AlertCircle, Bot, Sparkles } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("يرجى ملء جميع الحقول المطلوبة.");
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await login(email, password);
      if (!result.success) {
        setError(result.error || "فشل تسجيل الدخول. يرجى التحقق من بيانات الاعتماد.");
      }
    } catch {
      setError("حدث خطأ غير متوقع. يرجى المحاولة لاحقاً.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-emerald-500/8 rounded-full blur-3xl -z-10" />
      <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-teal-500/6 rounded-full blur-3xl -z-10" />
      <div className="absolute top-1/2 left-1/2 w-[300px] h-[300px] bg-blue-500/5 rounded-full blur-3xl -z-10 -translate-x-1/2 -translate-y-1/2" />

      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-10">
          <div className="w-20 h-20 bg-gradient-to-tr from-emerald-400 to-teal-600 rounded-3xl flex items-center justify-center shadow-2xl shadow-emerald-500/30 mb-5 transform hover:scale-105 transition-transform duration-300 relative">
            <Bot className="w-10 h-10 text-slate-950 stroke-[2]" />
            <div className="absolute -top-1.5 -left-1.5 w-5 h-5 bg-amber-400 rounded-full flex items-center justify-center">
              <Sparkles className="w-3 h-3 text-slate-900 stroke-[2.5]" />
            </div>
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-blue-400 bg-clip-text text-transparent">
            رسن
          </h1>
          <p className="text-sm text-slate-400 mt-2">منصة الشات بوت الذكي للشركات</p>
        </div>

        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl">
          <h2 className="text-xl font-bold text-slate-100 mb-6 text-center">
            تسجيل الدخول إلى حسابك
          </h2>

          {error && (
            <div className="mb-6 p-4 bg-rose-500/15 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-300 text-sm leading-relaxed">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label htmlFor="email" className="text-xs font-semibold text-slate-400 block mr-1">
                البريد الإلكتروني
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-500">
                  <Mail className="w-5 h-5" />
                </div>
                <input
                  id="email"
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 rounded-xl py-3 pr-10 pl-4 text-slate-100 placeholder-slate-600 outline-none transition-all duration-200"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-xs font-semibold text-slate-400 block mr-1">
                كلمة المرور
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-5 h-5" />
                </div>
                <input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 rounded-xl py-3 pr-10 pl-4 text-slate-100 placeholder-slate-600 outline-none transition-all duration-200"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold py-3.5 px-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/10 hover:shadow-emerald-500/20 transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none disabled:shadow-none"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>جاري تسجيل الدخول...</span>
                </>
              ) : (
                <span>دخول</span>
              )}
            </button>
          </form>
        </div>

        <div className="mt-8 grid grid-cols-3 gap-3 text-center">
          {[
            { label: "50 محادثة/شهر", sub: "في الخطة المجانية" },
            { label: "PDF & DOCX", sub: "ارفع بياناتك فوراً" },
            { label: "موقع + تيليجرام", sub: "قنوات متعددة" },
          ].map((item, i) => (
            <div key={i} className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-3">
              <p className="text-xs font-bold text-slate-300">{item.label}</p>
              <p className="text-[10px] text-slate-600 mt-0.5">{item.sub}</p>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-slate-700 mt-6 leading-relaxed">
          © 2026 رسن — جميع الحقوق محفوظة
        </p>
      </div>
    </main>
  );
}
