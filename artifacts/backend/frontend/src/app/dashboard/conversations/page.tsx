"use client";

import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { 
  Search, 
  MessageSquare, 
  Bot, 
  User, 
  Calendar, 
  Clock, 
  ChevronLeft, 
  Loader2,
  PhoneCall
} from "lucide-react";

interface ConversationItem {
  id: string;
  customer_phone: string;
  status: "active" | "handoff" | "closed";
  ai_mode: boolean;
  started_at: string;
  last_message_at: string;
  message_count: number;
}

type TabType = "all" | "active" | "handoff" | "closed";

export default function ConversationsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("all");

  const tenantId = user?.tenant_id;

  // Fetch Conversations list using React Query
  const { data: conversations = [], isLoading } = useQuery<ConversationItem[]>({
    queryKey: ["conversations", tenantId, activeTab],
    queryFn: async () => {
      if (!tenantId) return [];
      let url = `/api/v1/tenants/${tenantId}/conversations`;
      if (activeTab !== "all") {
        url += `?status=${activeTab}`;
      }
      const res = await fetch(url);
      if (!res.ok) throw new Error("فشل في جلب قائمة المحادثات");
      return res.json();
    },
    enabled: !!tenantId,
    // Poll list every 10 seconds to show incoming customer messages
    refetchInterval: 10000,
  });

  // Mask Phone Number Helper (e.g. +96650***1234)
  const maskPhoneNumber = (phone: string) => {
    if (!phone) return "";
    const cleaned = phone.replace(/\s+/g, "");
    if (cleaned.length > 7) {
      return `${cleaned.slice(0, 4)}***${cleaned.slice(-4)}`;
    }
    return cleaned;
  };

  // Filter conversations locally by search term
  const filteredConversations = conversations.filter((c) =>
    c.customer_phone.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return (
          <span className="text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2.5 py-0.5 rounded-full uppercase">
            نشطة
          </span>
        );
      case "handoff":
        return (
          <span className="text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-0.5 rounded-full uppercase animate-pulse">
            انتظار العميل
          </span>
        );
      case "closed":
        return (
          <span className="text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-0.5 rounded-full uppercase">
            مغلقة
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">سجل المحادثات</h1>
        <p className="text-sm text-slate-400 mt-1">
          مراقبة محادثات العملاء النشطة، والتدخل يدوياً لمساعدة العملاء، أو مراجعة جلسات الدردشة المؤرشفة.
        </p>
      </div>

      {/* Filters and Search Panel */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
        {/* Arabic Tabs */}
        <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-2xl w-full md:w-auto overflow-x-auto shrink-0">
          {(
            [
              { id: "all", label: "الكل" },
              { id: "active", label: "النشطة" },
              { id: "handoff", label: "قيد التحويل" },
              { id: "closed", label: "المغلقة" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 whitespace-nowrap ${
                activeTab === tab.id
                  ? "bg-slate-800 text-emerald-400 shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="relative w-full md:max-w-xs">
          <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-slate-500">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            placeholder="البحث برقم الهاتف..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-2xl py-2.5 pr-10 pl-4 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
          />
        </div>
      </div>

      {/* Conversations Grid / List */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
        {isLoading ? (
          <div className="py-24 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            <span className="text-sm text-slate-400">جاري تحميل جلسات الدردشة...</span>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="py-24 text-center">
            <MessageSquare className="w-12 h-12 text-slate-700 mx-auto mb-3" />
            <p className="font-bold text-slate-400">لا توجد محادثات مطابقة</p>
            <p className="text-xs text-slate-600 mt-1">لا توجد جلسات دردشة مسجلة حالياً ضمن هذا التصنيف.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => router.push(`/dashboard/conversations/${conv.id}`)}
                className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-900/40 cursor-pointer transition-all duration-250 group border-r-4 border-transparent hover:border-emerald-500"
              >
                {/* Right side information (RTL context) */}
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-slate-800 group-hover:bg-slate-700/80 rounded-2xl flex items-center justify-center text-slate-400 group-hover:text-emerald-400 border border-slate-700 transition-colors duration-200 shrink-0">
                    <PhoneCall className="w-5 h-5 stroke-[2]" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5">
                      <span className="font-bold text-slate-200 group-hover:text-slate-100 transition-colors duration-150">
                        {maskPhoneNumber(conv.customer_phone)}
                      </span>
                      {getStatusBadge(conv.status)}
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 font-medium">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-600" />
                        بدأت: {new Date(conv.started_at).toLocaleDateString("ar-EG")}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3.5 h-3.5 text-slate-600" />
                        {conv.message_count} رسائل
                      </span>
                      {conv.ai_mode ? (
                        <span className="flex items-center gap-1 text-emerald-500/80">
                          <Bot className="w-3.5 h-3.5" /> مجيب آلي
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-blue-400/80">
                          <User className="w-3.5 h-3.5" /> تحكم بشري
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Left side actions and timestamp */}
                <div className="flex items-center justify-between sm:justify-end gap-6 shrink-0">
                  <div className="text-left space-y-1">
                    <span className="text-[10px] text-slate-500 block">آخر رسالة</span>
                    <span className="text-xs text-slate-400 font-mono flex items-center gap-1 justify-end">
                      <Clock className="w-3.5 h-3.5 text-slate-600" />
                      {new Date(conv.last_message_at).toLocaleTimeString("ar-EG", {
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </span>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-emerald-400 transition-all duration-200 group-hover:translate-x-1">
                    <ChevronLeft className="w-5 h-5" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
