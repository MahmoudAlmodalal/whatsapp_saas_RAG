import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import {
  UserCheck,
  Bot,
  Clock,
  AlertTriangle,
  Cpu,
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertCircle
} from "lucide-react";

interface PendingHandoff {
  conversation_id: string;
  customer_phone: string;
  ai_summary: string | null;
  last_message_at: string;
  message_count: number;
  handoff_reason: string | null;
  assigned_agent_id: string | null;
}

interface PendingHandoffsResponse {
  total: number;
  items: PendingHandoff[];
}

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function HandoffsPage() {
  const { user } = useAuth();
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const tenantId = user?.tenant_id;

  const { data, isLoading } = useQuery<PendingHandoffsResponse>({
    queryKey: ["pendingHandoffs", tenantId],
    queryFn: async () => {
      if (!tenantId) return { total: 0, items: [] };
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}/handoffs/pending`);
      if (!res.ok) throw new Error("فشل في تحميل قائمة التحويل المعلقة");
      return res.json();
    },
    enabled: !!tenantId,
    refetchInterval: 5000,
  });

  const pendingItems = data?.items || [];

  const maskPhoneNumber = (phone: string) => {
    if (!phone) return "";
    const cleaned = phone.replace(/\s+/g, "");
    if (cleaned.length > 7) return `${cleaned.slice(0, 4)}***${cleaned.slice(-4)}`;
    return cleaned;
  };

  const acceptMutation = useMutation({
    mutationFn: async (convId: string) => {
      setErrorMsg("");
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: user?.id }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل استلام المحادثة");
      }
      return { convId };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["pendingHandoffs", tenantId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] });
      setSuccessMsg("تم استلام المحادثة بنجاح.");
      setTimeout(() => setSuccessMsg(""), 3000);
      navigate(`/dashboard/conversations/${data.convId}`);
    },
    onError: (err: Error) => setErrorMsg(err.message),
  });

  const resolveMutation = useMutation({
    mutationFn: async (convId: string) => {
      setErrorMsg("");
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ re_enable_ai: true }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل تفعيل الرد الآلي");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pendingHandoffs", tenantId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] });
      setSuccessMsg("تم إنهاء التحويل وإعادة تفعيل الذكاء الاصطناعي بنجاح.");
      setTimeout(() => setSuccessMsg(""), 3000);
    },
    onError: (err: Error) => setErrorMsg(err.message),
  });

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">قائمة انتظار التدخل البشري</h1>
        <p className="text-sm text-slate-400 mt-1">
          المحادثات التي تم تحويلها من الذكاء الاصطناعي وتنتظر استلامها من قِبَل موظف خدمة العملاء.
        </p>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-start gap-3 text-emerald-400 text-sm animate-fade-in">
          <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3 text-rose-400 text-sm animate-fade-in">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {isLoading ? (
        <div className="py-24 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
          <span className="text-sm text-slate-400">جاري تحميل قائمة الانتظار...</span>
        </div>
      ) : pendingItems.length === 0 ? (
        <div className="py-20 bg-slate-900/20 border border-slate-800 rounded-3xl text-center">
          <div className="w-16 h-16 bg-emerald-500/5 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/10">
            <CheckCircle2 className="w-8 h-8 text-emerald-500" />
          </div>
          <p className="font-bold text-slate-300">رائع! قائمة الانتظار فارغة</p>
          <p className="text-xs text-slate-500 mt-1">الذكاء الاصطناعي يتعامل مع جميع العملاء بكفاءة حالياً.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {pendingItems.map((item) => (
            <div
              key={item.conversation_id}
              className="bg-slate-900/40 hover:bg-slate-900/60 border border-slate-800 rounded-3xl p-6 transition-all duration-200 shadow-xl flex flex-col lg:flex-row lg:items-start justify-between gap-6"
            >
              <div className="flex-1 space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-base font-extrabold text-slate-100">
                    {maskPhoneNumber(item.customer_phone)}
                  </span>
                  {item.handoff_reason && (
                    <span className="text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      {item.handoff_reason}
                    </span>
                  )}
                  {item.assigned_agent_id && (
                    <span className="text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2.5 py-0.5 rounded-full">
                      مستلمة من وكيل آخر
                    </span>
                  )}
                </div>

                {item.ai_summary && (
                  <div className="p-3.5 bg-slate-950/40 border border-slate-800 rounded-2xl">
                    <div className="flex items-center gap-1.5 text-emerald-400 font-bold text-[10px] mb-1.5">
                      <Cpu className="w-3 h-3" /> ملخص الذكاء الاصطناعي:
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">{item.ai_summary}</p>
                  </div>
                )}

                <div className="flex flex-wrap gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-600" />
                    آخر رسالة: {new Date(item.last_message_at).toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Bot className="w-3.5 h-3.5 text-slate-600" />
                    {item.message_count} رسالة
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-2.5 shrink-0">
                <button
                  onClick={() => acceptMutation.mutate(item.conversation_id)}
                  disabled={acceptMutation.isPending}
                  className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold px-5 py-2.5 rounded-xl flex items-center justify-center gap-2 shadow-lg transition-all duration-200 text-sm"
                >
                  {acceptMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserCheck className="w-4 h-4" />}
                  <span>استلام المحادثة</span>
                </button>
                <button
                  onClick={() => navigate(`/dashboard/conversations/${item.conversation_id}`)}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-5 py-2.5 rounded-xl flex items-center justify-center gap-2 border border-slate-700 transition-all duration-200 text-sm"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>عرض المحادثة</span>
                </button>
                <button
                  onClick={() => resolveMutation.mutate(item.conversation_id)}
                  disabled={resolveMutation.isPending}
                  className="bg-slate-900 hover:bg-emerald-500/5 text-slate-400 hover:text-emerald-400 font-bold px-5 py-2.5 rounded-xl flex items-center justify-center gap-2 border border-slate-800 hover:border-emerald-500/20 transition-all duration-200 text-sm"
                >
                  {resolveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
                  <span>إعادة تفعيل الذكاء الاصطناعي</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
