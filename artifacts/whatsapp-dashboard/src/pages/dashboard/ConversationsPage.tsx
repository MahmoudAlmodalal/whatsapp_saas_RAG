import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, AlertCircle, CheckCircle, Loader2, Brain, Send } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface UnansweredQ {
  id: string;
  question: string;
  session_id: string;
  created_at: string;
}

export default function ConversationsPage() {
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [learned, setLearned] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery<{ unanswered_questions: UnansweredQ[] }>({
    queryKey: ["unanswered"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/analytics`, { credentials: "include" });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    refetchInterval: 20000,
  });

  const learnMut = useMutation({
    mutationFn: async ({ question, answer, id }: { question: string; answer: string; id: string }) => {
      const res = await fetch(`${BASE}/api/v1/learn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ question, answer, company_id: "default", unanswered_id: id }),
      });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    onSuccess: (_, vars) => {
      setLearned((s) => new Set([...s, vars.id]));
      qc.invalidateQueries({ queryKey: ["unanswered"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });

  const questions = data?.unanswered_questions ?? [];

  return (
    <div className="p-8 space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-100">الأسئلة غير المُجاب عنها</h1>
        <p className="text-slate-400 text-sm mt-1">أجب على هذه الأسئلة وعلّم نصيح ليجيب عليها تلقائياً في المستقبل</p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
        </div>
      ) : !questions.length ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 bg-slate-900 border border-slate-800 rounded-2xl">
          <CheckCircle className="w-12 h-12 text-emerald-500" />
          <p className="text-slate-300 font-medium">ممتاز! لا توجد أسئلة بدون إجابة</p>
          <p className="text-slate-500 text-sm">نصيح يجيب على كل الأسئلة بنجاح</p>
        </div>
      ) : (
        <div className="space-y-4">
          {questions.map((q) => {
            const done = learned.has(q.id);
            return (
              <div key={q.id} className={`bg-slate-900 border rounded-2xl p-5 space-y-4 transition-all ${
                done ? "border-emerald-500/30 opacity-60" : "border-slate-800"}`}>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-amber-500/10 rounded-xl flex items-center justify-center shrink-0 mt-0.5">
                    <AlertCircle className="w-4 h-4 text-amber-400" />
                  </div>
                  <div className="flex-1">
                    <p className="text-slate-200 text-sm font-medium leading-relaxed">{q.question}</p>
                    <p className="text-slate-500 text-xs mt-1">{q.session_id} · {new Date(q.created_at).toLocaleString("ar-SA")}</p>
                  </div>
                  {done && <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />}
                </div>

                {!done && (
                  <div className="space-y-3 border-t border-slate-800 pt-4">
                    <textarea
                      value={answers[q.id] ?? ""}
                      onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))}
                      placeholder="اكتب الإجابة الصحيحة هنا..."
                      rows={3}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:border-emerald-500 resize-none"
                    />
                    <div className="flex gap-3 items-center">
                      <button
                        onClick={() => learnMut.mutate({ question: q.question, answer: answers[q.id] ?? "", id: q.id })}
                        disabled={!answers[q.id]?.trim() || learnMut.isPending}
                        className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-50">
                        {learnMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
                        علّم نصيح هذه الإجابة
                      </button>
                      <p className="text-slate-500 text-xs">ستُضاف تلقائياً لقاعدة المعرفة</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
