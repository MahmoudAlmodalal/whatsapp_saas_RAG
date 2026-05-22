"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { 
  ArrowRight, 
  Bot, 
  User, 
  Send, 
  Loader2, 
  UserCheck, 
  Play, 
  AlertTriangle,
  Cpu,
  MessageSquare
} from "lucide-react";

interface MessageItem {
  id: string;
  role: "customer" | "ai" | "agent";
  content: string;
  created_at: string;
  tokens_used?: number;
  model_used?: string;
  latency_ms?: number;
}

interface ConversationDetail {
  id: string;
  customer_phone: string;
  status: "active" | "handoff" | "closed";
  ai_mode: boolean;
  started_at: string;
  last_message_at: string;
  metadata: {
    assigned_agent_id?: string;
    handoff_events?: Array<{
      handoff_id: string;
      reason: string;
      timestamp: string;
      assigned_agent: string | null;
      ai_summary?: string;
    }>;
  };
  messages: MessageItem[];
}

export default function ConversationDetailPage({ params }: { params: { id: string } }) {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const [inputText, setInputText] = useState("");
  const [actionError, setActionError] = useState("");

  const convId = params.id;
  const tenantId = user?.tenant_id;

  // Fetch Conversation Details
  const { data: conversation, isLoading } = useQuery<ConversationDetail>({
    queryKey: ["conversation", tenantId, convId],
    queryFn: async () => {
      if (!tenantId || !convId) throw new Error("بيانات غير كافية");
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}`);
      if (!res.ok) throw new Error("فشل في تحميل تفاصيل المحادثة");
      return res.json();
    },
    enabled: !!tenantId && !!convId,
    // Poll the single conversation view every 3 seconds to keep chat real-time
    refetchInterval: 3000,
  });

  // Scroll to bottom on new messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (conversation?.messages) {
      scrollToBottom();
    }
  }, [conversation?.messages]);

  // Mask Phone Number
  const maskPhoneNumber = (phone: string) => {
    if (!phone) return "";
    const cleaned = phone.replace(/\s+/g, "");
    if (cleaned.length > 7) {
      return `${cleaned.slice(0, 4)}***${cleaned.slice(-4)}`;
    }
    return cleaned;
  };

  // ── Mutatons ──────────────────────────────────────────────────────────────

  // Accept Handoff
  const acceptHandoffMutation = useMutation({
    mutationFn: async () => {
      setActionError("");
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: user?.id }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل استلام المحادثة");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", tenantId, convId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] });
    },
    onError: (err: Error) => {
      setActionError(err.message);
    }
  });

  // Resolve Handoff
  const resolveHandoffMutation = useMutation({
    mutationFn: async (reEnableAi: boolean) => {
      setActionError("");
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ re_enable_ai: reEnableAi }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل إنهاء وضع التحويل");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", tenantId, convId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] });
    },
    onError: (err: Error) => {
      setActionError(err.message);
    }
  });

  // Trigger Handoff Manually
  const triggerHandoffMutation = useMutation({
    mutationFn: async () => {
      setActionError("");
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}/handoff/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "تدخل يدوي من لوحة التحكم" }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل إيقاف الذكاء الاصطناعي");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", tenantId, convId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] });
    },
    onError: (err: Error) => {
      setActionError(err.message);
    }
  });

  // Send Message
  const sendMessageMutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await fetch(`/api/v1/tenants/${tenantId}/conversations/${convId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل إرسال الرسالة");
      }
      return res.json();
    },
    onSuccess: () => {
      setInputText("");
      queryClient.invalidateQueries({ queryKey: ["conversation", tenantId, convId] });
      setTimeout(scrollToBottom, 100);
    },
    onError: (err: Error) => {
      setActionError(err.message);
    }
  });

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    sendMessageMutation.mutate(inputText);
  };

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
        <span className="text-sm text-slate-400">جاري تحميل تفاصيل المحادثة...</span>
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="p-8 text-center text-slate-400">
        المحادثة المطلوبة غير موجودة أو لا تملك صلاحية الوصول إليها.
      </div>
    );
  }

  const isAssignedToMe = conversation.metadata?.assigned_agent_id === user?.id;
  const hasAgentAssigned = !!conversation.metadata?.assigned_agent_id;
  
  // Latest handoff AI Summary if present
  const latestHandoff = conversation.metadata?.handoff_events?.slice(-1)[0];
  const aiSummaryText = latestHandoff?.ai_summary;

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col -m-8 relative">
      {/* 1. Top Navigation & Details Header */}
      <header className="px-8 py-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/dashboard/conversations")}
            className="p-2 hover:bg-slate-800 rounded-xl text-slate-400 hover:text-slate-200 transition-colors duration-150"
            title="رجوع"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
          
          <div>
            <div className="flex items-center gap-3">
              <span className="font-extrabold text-slate-100 text-lg">
                {maskPhoneNumber(conversation.customer_phone)}
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase border ${
                conversation.status === "active"
                  ? "bg-sky-500/10 text-sky-400 border-sky-500/20"
                  : conversation.status === "handoff"
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse"
                  : "bg-slate-800 text-slate-400 border-slate-700"
              }`}>
                {conversation.status === "active"
                  ? "نشطة"
                  : conversation.status === "handoff"
                  ? "انتظار عميل بشري"
                  : "مغلقة"}
              </span>
            </div>
            
            <p className="text-[10px] text-slate-500 mt-0.5">معرف الجلسة: {conversation.id}</p>
          </div>
        </div>

        {/* AI mode status badge */}
        <div className="flex items-center gap-2.5 bg-slate-950/80 px-4 py-2 rounded-xl border border-slate-800">
          {conversation.ai_mode ? (
            <>
              <Bot className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-emerald-400">الذكاء الاصطناعي يدير الجلسة</span>
            </>
          ) : (
            <>
              <User className="w-4 h-4 text-blue-400" />
              <span className="text-xs font-bold text-blue-400">تحكم بشري يدوي</span>
            </>
          )}
        </div>
      </header>

      {/* Action Error Alert */}
      {actionError && (
        <div className="mx-8 mt-4 p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center gap-2 text-rose-400 text-xs shrink-0 animate-fade-in">
          <AlertTriangle className="w-4 h-4" />
          <span>{actionError}</span>
        </div>
      )}

      {/* AI Summary Banner (if in Handoff and has summary) */}
      {conversation.status === "handoff" && aiSummaryText && (
        <div className="mx-8 mt-4 p-4 bg-slate-900 border border-amber-500/20 rounded-2xl shrink-0 animate-fade-in">
          <div className="flex items-center gap-2 text-amber-400 font-bold text-xs mb-1">
            <Cpu className="w-4 h-4" /> ملخص الذكاء الاصطناعي للمشكلة:
          </div>
          <p className="text-xs text-slate-300 leading-relaxed font-medium">{aiSummaryText}</p>
        </div>
      )}

      {/* 2. Messages List Body */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {conversation.messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-2">
            <MessageSquare className="w-12 h-12 stroke-[1]" />
            <p className="text-sm font-medium">لا توجد رسائل مسجلة بعد في هذه الجلسة</p>
          </div>
        ) : (
          conversation.messages.map((msg) => {
            const isCustomer = msg.role === "customer";
            const isAI = msg.role === "ai";

            return (
              <div
                key={msg.id}
                className={`flex flex-col max-w-[70%] ${
                  isCustomer ? "mr-auto items-end" : "ml-auto items-start"
                }`}
              >
                {/* Bubble Container */}
                <div
                  className={`px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
                    isCustomer
                      ? "bg-blue-600 text-slate-100 rounded-br-none"
                      : isAI
                      ? "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none"
                      : "bg-emerald-600 text-slate-100 rounded-bl-none"
                  }`}
                >
                  <p className="whitespace-pre-line">{msg.content}</p>
                </div>

                {/* Sub-bubble info (Sender & Timestamp & AI Stats) */}
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500 font-medium">
                  <span>
                    {isCustomer ? "العميل" : isAI ? "الرد الآلي" : "الوكيل البشري"}
                  </span>
                  <span>•</span>
                  <span className="font-mono">
                    {new Date(msg.created_at).toLocaleTimeString("ar-EG", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>

                  {/* AI Metadata Stats */}
                  {isAI && (msg.tokens_used || msg.latency_ms) && (
                    <>
                      <span>•</span>
                      <span className="text-slate-600 flex items-center gap-1">
                        <Cpu className="w-3 h-3" />
                        <span>
                          {msg.model_used && `${msg.model_used} | `}
                          {msg.latency_ms && `${msg.latency_ms}ms`}
                          {msg.tokens_used && ` | ${msg.tokens_used} tokens`}
                        </span>
                      </span>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 3. Bottom Control Console */}
      <footer className="px-8 py-5 bg-slate-900 border-t border-slate-800 shrink-0">
        {conversation.status === "handoff" && !isAssignedToMe ? (
          /* Handoff Status — Takeover panel */
          <div className="bg-slate-950/60 p-4 border border-slate-800 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-right">
              <h4 className="font-bold text-amber-400 text-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" /> محادثة معلقة في وضع الانتظار
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                {hasAgentAssigned 
                  ? "هذه الجلسة مستلمة من قِبل وكيل آخر حالياً."
                  : "يحتاج العميل إلى تدخل عميل خدمة عملاء بشري لحل استفساره."}
              </p>
            </div>
            
            <button
              onClick={() => acceptHandoffMutation.mutate()}
              disabled={acceptHandoffMutation.isPending}
              className="w-full md:w-auto bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold px-6 py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/10 transition-all duration-200"
            >
              {acceptHandoffMutation.isPending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <UserCheck className="w-5 h-5" />
              )}
              <span>{hasAgentAssigned ? "استلام وتغيير الوكيل" : "استلام المحادثة الآن"}</span>
            </button>
          </div>
        ) : conversation.status === "handoff" && isAssignedToMe ? (
          /* Handoff Status — Active Chatting (I have takeover) */
          <div className="space-y-4">
            {/* Resolution buttons bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-950/40 p-3 border border-slate-800/80 rounded-2xl">
              <span className="text-xs text-slate-400 font-medium">التحكم اليدوي مفعل للحساب الخاص بك</span>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => resolveHandoffMutation.mutate(true)}
                  disabled={resolveHandoffMutation.isPending}
                  className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 font-bold text-xs px-4 py-2.5 rounded-xl border border-emerald-500/20 flex items-center gap-1.5 transition-all duration-200"
                >
                  <Play className="w-3.5 h-3.5" />
                  إعادة تفعيل الذكاء الاصطناعي
                </button>
                <button
                  onClick={() => resolveHandoffMutation.mutate(false)}
                  disabled={resolveHandoffMutation.isPending}
                  className="bg-slate-800 hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/20 text-slate-300 font-bold text-xs px-4 py-2.5 rounded-xl border border-slate-700 flex items-center gap-1.5 transition-all duration-200"
                >
                  إغلاق المحادثة نهائياً
                </button>
              </div>
            </div>

            {/* Message input form */}
            <form onSubmit={handleSendMessage} className="flex gap-3">
              <input
                type="text"
                placeholder="اكتب ردك هنا..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={sendMessageMutation.isPending}
                className="flex-1 bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl px-5 py-3.5 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
              />
              <button
                type="submit"
                disabled={sendMessageMutation.isPending || !inputText.trim()}
                className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold p-3.5 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/10 hover:shadow-emerald-500/20 transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none"
              >
                {sendMessageMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5 -rotate-90 transform" />
                )}
              </button>
            </form>
          </div>
        ) : conversation.status === "active" ? (
          /* Active Status — AI handling, Agent can manually intervene */
          <div className="bg-slate-950/60 p-4 border border-slate-800 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-right">
              <h4 className="font-bold text-emerald-400 text-sm flex items-center gap-2">
                <Bot className="w-4 h-4" /> المحادثة في الوضع الآلي
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                الذكاء الاصطناعي يستجيب حالياً للعميل تلقائياً بناءً على قاعدة معرفتك.
              </p>
            </div>
            
            <button
              onClick={() => triggerHandoffMutation.mutate()}
              disabled={triggerHandoffMutation.isPending}
              className="w-full md:w-auto bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 font-bold px-6 py-3 rounded-xl border border-amber-500/20 flex items-center justify-center gap-2 transition-all duration-200"
            >
              {triggerHandoffMutation.isPending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <User className="w-5 h-5" />
              )}
              <span>إيقاف الروبوت والتدخل يدوياً</span>
            </button>
          </div>
        ) : (
          /* Closed Status */
          <div className="bg-slate-950/60 p-4 border border-slate-800 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-right">
              <h4 className="font-bold text-slate-400 text-sm">محادثة مؤرشفة</h4>
              <p className="text-xs text-slate-500 mt-1">
                تم إغلاق هذه الجلسة وتصنيفها كجلسة منتهية.
              </p>
            </div>
            
            <button
              onClick={() => resolveHandoffMutation.mutate(true)}
              disabled={resolveHandoffMutation.isPending}
              className="w-full md:w-auto bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-6 py-3 rounded-xl border border-slate-700 transition-all duration-200"
            >
              {resolveHandoffMutation.isPending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Bot className="w-5 h-5" />
              )}
              <span>إعادة تفعيل المجيب الآلي</span>
            </button>
          </div>
        )}
      </footer>
    </div>
  );
}
