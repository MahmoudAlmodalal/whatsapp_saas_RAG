import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  MessageSquare,
  FileText,
  UserCheck,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  BarChart3,
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface Analytics {
  total_questions: number;
  answered_count: number;
  answer_rate: number;
  unanswered_count: number;
  handoff_count: number;
  open_handoffs: number;
  document_count: number;
  conversation_count: number;
  unanswered_questions: Array<{ id: string; question: string; session_id: string }>;
  top_repeated_questions: Array<{ question: string; count: number }>;
}

function StatCard({ label, value, icon: Icon, color, sub }: {
  label: string; value: string | number; icon: React.ElementType; color: string; sub?: string;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-slate-400 text-sm font-medium">{label}</span>
        <div className={`w-10 h-10 ${color} rounded-xl flex items-center justify-center`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <p className="text-3xl font-black text-slate-100">{value}</p>
      {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
    </div>
  );
}

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery<Analytics>({
    queryKey: ["analytics"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/analytics`, { credentials: "include" });
      if (!res.ok) throw new Error("فشل تحميل الإحصائيات");
      return res.json();
    },
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Brain className="w-8 h-8 text-emerald-500 animate-pulse" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-slate-400 text-sm">تعذر الاتصال بخادم نصيح — تأكد من تشغيل الخلفية Python</p>
        <p className="text-slate-600 text-xs">GET /api/v1/analytics</p>
      </div>
    );
  }

  const maxCount = Math.max(...(data.top_repeated_questions?.map((q) => q.count) ?? [1]), 1);

  return (
    <div className="p-8 space-y-8" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-100">لوحة تحكم نصيح</h1>
        <p className="text-slate-400 text-sm mt-1">وكيل دعم العملاء الذكي · RAG + GPT-4o · ثنائي اللغة</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="إجمالي الأسئلة" value={data.total_questions} icon={MessageSquare}
          color="bg-blue-500/10 text-blue-400" sub="من جميع القنوات" />
        <StatCard label="معدل الإجابة" value={`${data.answer_rate}%`} icon={TrendingUp}
          color="bg-emerald-500/10 text-emerald-400" sub={`${data.answered_count} إجابة صحيحة`} />
        <StatCard label="المستندات" value={data.document_count} icon={FileText}
          color="bg-violet-500/10 text-violet-400" sub="في قاعدة المعرفة" />
        <StatCard label="تحويلات مفتوحة" value={data.open_handoffs} icon={UserCheck}
          color={data.open_handoffs > 0 ? "bg-amber-500/10 text-amber-400" : "bg-slate-700/50 text-slate-400"}
          sub={`${data.handoff_count} إجمالي التحويلات`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            <h2 className="font-bold text-slate-100">أكثر الأسئلة تكراراً</h2>
          </div>
          {!data.top_repeated_questions?.length ? (
            <div className="flex flex-col items-center justify-center py-10 gap-2">
              <HelpCircle className="w-8 h-8 text-slate-600" />
              <p className="text-slate-500 text-sm">لا توجد محادثات بعد</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.top_repeated_questions.slice(0, 8).map((q, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300 text-sm truncate max-w-[75%]">{q.question}</span>
                    <span className="text-emerald-400 text-xs font-bold">{q.count}×</span>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-l from-emerald-500 to-teal-400 rounded-full"
                      style={{ width: `${(q.count / maxCount) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <AlertCircle className="w-5 h-5 text-amber-400" />
            <h2 className="font-bold text-slate-100">أسئلة بدون إجابة</h2>
            <span className="bg-amber-500/10 text-amber-400 text-xs px-2 py-0.5 rounded-full border border-amber-500/20 mr-auto">
              {data.unanswered_count}
            </span>
          </div>
          {!data.unanswered_questions?.length ? (
            <div className="flex flex-col items-center justify-center py-10 gap-2">
              <CheckCircle className="w-8 h-8 text-emerald-500" />
              <p className="text-slate-500 text-sm">رائع! لا توجد أسئلة بدون إجابة</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {data.unanswered_questions.map((q) => (
                <div key={q.id} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
                  <p className="text-slate-300 text-sm leading-relaxed">{q.question}</p>
                  <p className="text-slate-500 text-xs mt-1">{q.session_id}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-5 h-5 text-emerald-400" />
          <h2 className="font-bold text-slate-100">حالة مكونات النظام</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { label: "RAG Engine", ok: true },
            { label: "ChromaDB", ok: true },
            { label: "SQLite DB", ok: true },
            { label: "Strategy Pattern", ok: true },
            { label: "Channel Factory", ok: true },
            { label: "Learning Loop", ok: true },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2 bg-slate-800/50 rounded-xl px-4 py-2.5">
              <div className={`w-2 h-2 rounded-full ${item.ok ? "bg-emerald-400" : "bg-red-400"} animate-pulse`} />
              <span className="text-slate-300 text-sm">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
