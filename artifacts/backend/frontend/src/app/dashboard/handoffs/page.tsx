"use client";

import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
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

export default function HandoffsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const tenantId = user?.tenant_id;

  // Fetch Pending Handoffs
  const { data, isLoading } = useQuery<PendingHandoffsResponse>({
    queryKey: ["pendingHandoffs", tenantId],
    queryFn: async () => {
      if (!tenantId) return { total: 0, items: [] };
      const res = await fetch(`/api/v1/tenants/${tenantId}/handoffs/pending`);
      if (!res.ok) throw new Error("فشل في تحميل قائمة التحويل المعلقة");
      return res.json();
    },
    enabled: !!tenantId,
    // Poll the handoffs queue every 5 seconds for new customer requests
    refetchInterval: 5000,
  });

  const pendingItems = data?.items || [];

  // Mask Phone Number
  const maskPhoneNumber = (phone: string) => {
    if (!phone) return "";
    const cleaned = phone.replace(/\s+/g, "");
    if (cleaned.length > 7) {
      return `${cleaned.slice(0, 4)}***${cleaned.slice(-4)}`;
    }
    return cleaned;
  };

  // Accept Handoff Mutation
  const acceptMutation = useMutation({
    mutationFn: async (convId: string) => {
      setErrorMsg("");
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/accept`, {
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
      
      // Redirect directly to the chat screen
      router.push(`/dashboard/conversations/${data.convId}`);
    },
    onError: (err: Error) => {
      setErrorMsg(err.message);
    }
  });

  // Resolve & Re-enable AI Mutation
  const resolveMutation = useMutation({
    mutationFn: async (convId: string) => {
      setErrorMsg("");
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/resolve`, {
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
    onError: (err: Error) => {
      setErrorMsg(err.message);
    }
  });

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">قائمة انتظار التدخل البشري</h1>
        <p className="text-sm text-slate-400 mt-1">
          المحادثات التي تم تحويلها من الذكاء الاصطناعي وتنتظر استلامها من قِبَل موظف خدمة العملاء.
        </p>
      </div>

      {/* Messages / Alerts */}
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

      {/* Main Queue Dashboard */}
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
              {/* Content Block */}
              <div className="flex-1 space-y-4">
                {/* Meta details header */}
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-base font-extrabold text-slate-100">
                    {maskPhoneNumber(item.customer_phone)}
                  </span>
                  
                  {item.handoff_reason && (
                    <span className="text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      السبب: {item.handoff_reason}
                    </span>
                  )}
                  
                  <span className="text-xs text-slate-500 font-mono flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    قبل: {new Date(item.last_message_at).toLocaleTimeString("ar-EG", {
                      hour: "2-digit",
                      minute: "2-digit"
                    })}
                  </span>

                  <span className="text-xs text-slate-500 font-mono">
                    {item.message_count} رسائل في الجلسة
                  </span>
                </div>

                {/* AI generated summary */}
                {item.ai_summary ? (
                  <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-2xl">
                    <div className="flex items-center gap-2 text-xs font-bold text-slate-400 mb-1.5">
                      <Cpu className="w-4 h-4 text-emerald-500" />
                      ملخص المشكلة بواسطة الذكاء الاصطناعي:
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-medium">
                      {item.ai_summary}
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">لا يوجد ملخص متاح لهذه المحادثة.</p>
                )}
              </div>

              {/* Actions Block */}
              <div className="flex flex-wrap lg:flex-col items-center lg:items-stretch justify-end gap-3 shrink-0">
                <button
                  onClick={() => acceptMutation.mutate(item.conversation_id)}
                  disabled={acceptMutation.isPending || resolveMutation.isPending}
                  className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-5 py-2.5 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/10 transition-all duration-200"
                >
                  {acceptMutation.isPending && acceptMutation.variables === item.conversation_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <UserCheck className="w-4 h-4" />
                  )}
                  <span>استلام الآن والدردشة</span>
                </button>

                <button
                  onClick={() => resolveMutation.mutate(item.conversation_id)}
                  disabled={acceptMutation.isPending || resolveMutation.isPending}
                  className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 font-bold px-5 py-2.5 rounded-xl border border-slate-700 flex items-center justify-center gap-2 transition-all duration-200"
                >
                  {resolveMutation.isPending && resolveMutation.variables === item.conversation_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Bot className="w-4 h-4" />
                  )}
                  <span>إرجاع للذكاء الاصطناعي</span>
                </button>

                <button
                  onClick={() => router.push(`/dashboard/conversations/${item.conversation_id}`)}
                  className="text-slate-400 hover:text-slate-200 text-xs font-semibold py-2 px-3 flex items-center justify-center gap-1 hover:underline transition-all"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  معاينة تفاصيل الجلسة
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
