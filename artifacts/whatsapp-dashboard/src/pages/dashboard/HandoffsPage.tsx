import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserCheck, Bot, User, CheckCircle, Clock, Send, ChevronDown, ChevronUp, Loader2, AlertCircle } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface HandoffItem {
  id: string;
  session_id: string;
  trigger_reason: string;
  status: string;
  agent_reply: string | null;
  created_at: string;
  history: Array<{ role: string; content: string }>;
}

export default function HandoffsPage() {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [replyTexts, setReplyTexts] = useState<Record<string, string>>({});
  const [learnTexts, setLearnTexts] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<"open" | "closed" | "all">("open");

  const { data, isLoading } = useQuery<{ handoffs: HandoffItem[] }>({
    queryKey: ["handoffs", filter],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/handoffs?status=${filter}&company_id=default`, { credentials: "include" });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    refetchInterval: 15000,
  });

  const replyMut = useMutation({
    mutationFn: async ({ id, reply }: { id: string; reply: string }) => {
      const res = await fetch(`${BASE}/api/v1/handoffs/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ agent_reply: reply }),
      });
      if (!res.ok) throw new Error("failed");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["handoffs"] }),
  });

  const learnMut = useMutation({
    mutationFn: async ({ question, answer }: { question: string; answer: string }) => {
      const res = await fetch(`${BASE}/api/v1/learn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ question, answer, company_id: "default" }),
      });
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
  });

  const filterBtns: Array<{ value: typeof filter; label: string }> = [
    { value: "open", label: "مفتوحة" },
    { value: "closed", label: "مغلقة" },
    { value: "all", label: "الكل" },
  ];

  return (
    <div className="p-8 space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-100">تحويلات الموظفين</h1>
        <p className="text-slate-400 text-sm mt-1">محادثات تحتاج تدخل بشري · أجب وعلّم نصيح</p>
      </div>

      <div className="flex gap-2">
        {filterBtns.map((b) => (
          <button key={b.value} onClick={() => setFilter(b.value)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === b.value
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
            }`}>
            {b.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 text-emerald-500 animate-spin" /></div>
      ) : !data?.handoffs?.length ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 bg-slate-900 border border-slate-800 rounded-2xl">
          <CheckCircle className="w-10 h-10 text-emerald-500" />
          <p className="text-slate-400">لا توجد تحويلات {filter === "open" ? "مفتوحة" : ""}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.handoffs.map((h) => {
            const isOpen = expanded === h.id;
            const userMsg = h.history.filter((m) => m.role === "user").slice(-1)[0]?.content ?? "—";
            return (
              <div key={h.id} className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
                <button onClick={() => setExpanded(isOpen ? null : h.id)}
                  className="w-full flex items-center gap-4 p-5 hover:bg-slate-800/30 transition-colors text-right">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    h.status === "open" ? "bg-amber-500/10" : "bg-emerald-500/10"}`}>
                    {h.status === "open"
                      ? <Clock className="w-5 h-5 text-amber-400" />
                      : <CheckCircle className="w-5 h-5 text-emerald-400" />}
                  </div>
                  <div className="flex-1 min-w-0 text-right">
                    <p className="text-slate-200 text-sm font-medium truncate">{userMsg}</p>
                    <p className="text-slate-500 text-xs mt-0.5">
                      {h.trigger_reason} · {new Date(h.created_at).toLocaleString("ar-SA")}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full border shrink-0 ${
                    h.status === "open"
                      ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"}`}>
                    {h.status === "open" ? "مفتوح" : "مغلق"}
                  </span>
                  {isOpen ? <ChevronUp className="w-4 h-4 text-slate-500 shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-500 shrink-0" />}
                </button>

                {isOpen && (
                  <div className="border-t border-slate-800 p-5 space-y-4">
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {h.history.map((m, i) => (
                        <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                          <div className={`flex items-start gap-2 max-w-[80%] ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                            <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                              m.role === "user" ? "bg-blue-500/20" : "bg-emerald-500/20"}`}>
                              {m.role === "user" ? <User className="w-3.5 h-3.5 text-blue-400" /> : <Bot className="w-3.5 h-3.5 text-emerald-400" />}
                            </div>
                            <div className={`rounded-xl px-3 py-2 text-sm ${
                              m.role === "user" ? "bg-blue-500/10 text-blue-100" : "bg-slate-800 text-slate-200"}`}>
                              {m.content}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {h.status === "open" && (
                      <div className="space-y-3 border-t border-slate-700 pt-4">
                        <div className="relative">
                          <textarea
                            value={replyTexts[h.id] ?? ""}
                            onChange={(e) => setReplyTexts((p) => ({ ...p, [h.id]: e.target.value }))}
                            placeholder="اكتب ردك على العميل..."
                            rows={3}
                            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:border-emerald-500 resize-none"
                          />
                        </div>
                        <div className="flex gap-3">
                          <button
                            onClick={() => replyMut.mutate({ id: h.id, reply: replyTexts[h.id] ?? "" })}
                            disabled={!replyTexts[h.id]?.trim() || replyMut.isPending}
                            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-50">
                            <Send className="w-4 h-4" /> إغلاق التحويل
                          </button>
                          <button
                            onClick={async () => {
                              const q = userMsg;
                              const a = replyTexts[h.id] ?? "";
                              if (!a.trim()) return;
                              await learnMut.mutateAsync({ question: q, answer: a });
                            }}
                            disabled={!replyTexts[h.id]?.trim() || learnMut.isPending}
                            className="flex items-center gap-2 bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 border border-violet-500/20 font-medium px-4 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-50">
                            {learnMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserCheck className="w-4 h-4" />}
                            أضف للمعرفة
                          </button>
                        </div>
                        {learnMut.isSuccess && (
                          <p className="text-emerald-400 text-xs">✓ تمت إضافة الإجابة لقاعدة المعرفة</p>
                        )}
                      </div>
                    )}

                    {h.agent_reply && (
                      <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4">
                        <p className="text-emerald-400 text-xs mb-1 font-medium">رد الموظف:</p>
                        <p className="text-slate-300 text-sm">{h.agent_reply}</p>
                      </div>
                    )}
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
