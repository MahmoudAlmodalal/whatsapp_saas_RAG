import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import {
  Search,
  MessageSquare,
  Bot,
  User,
  Calendar,
  Clock,
  ChevronLeft,
  Loader2,
  Globe,
  Send
} from "lucide-react";

interface ConversationItem {
  id: string;
  customer_phone?: string;
  customer_identifier: string;
  channel: "web" | "telegram";
  status: "active" | "handoff" | "closed";
  ai_mode: boolean;
  started_at: string;
  last_message_at: string;
  message_count: number;
}

type StatusTab = "all" | "active" | "handoff" | "closed";
type ChannelFilter = "all" | "web" | "telegram";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function ConversationsPage() {
  const { user } = useAuth();
  const [, navigate] = useLocation();
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState<StatusTab>("all");
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>("all");

  const tenantId = user?.tenant_id;

  const { data: conversations = [], isLoading } = useQuery<ConversationItem[]>({
    queryKey: ["conversations", tenantId, activeTab, channelFilter],
    queryFn: async () => {
      if (!tenantId) return [];
      const params = new URLSearchParams();
      if (activeTab !== "all") params.set("status", activeTab);
      if (channelFilter !== "all") params.set("channel", channelFilter);
      const qs = params.toString();
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}/conversations${qs ? `?${qs}` : ""}`);
      if (!res.ok) throw new Error("فشل في جلب قائمة المحادثات");
      return res.json();
    },
    enabled: !!tenantId,
    refetchInterval: 10000,
  });

  const getDisplayId = (conv: ConversationItem) => {
    const id = conv.customer_phone || conv.customer_identifier || "";
    if (!id) return "—";
    if (id.length > 12) return `${id.slice(0, 4)}***${id.slice(-4)}`;
    return id;
  };

  const filteredConversations = conversations.filter((c) => {
    const id = (c.customer_phone || c.customer_identifier || "").toLowerCase();
    return id.includes(searchTerm.toLowerCase());
  });

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
            تحويل لوكيل
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

  const getChannelBadge = (channel: string) => {
    if (channel === "telegram") {
      return (
        <span className="text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
          <Send className="w-2.5 h-2.5" /> تيليجرام
        </span>
      );
    }
    return (
      <span className="text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
        <Globe className="w-2.5 h-2.5" /> موقع
      </span>
    );
  };

  const statusTabs: { id: StatusTab; label: string }[] = [
    { id: "all",     label: "الكل" },
    { id: "active",  label: "النشطة" },
    { id: "handoff", label: "قيد التحويل" },
    { id: "closed",  label: "المغلقة" },
  ];

  const channelTabs: { id: ChannelFilter; label: string; icon?: React.ElementType }[] = [
    { id: "all",      label: "جميع القنوات" },
    { id: "web",      label: "موقع",     icon: Globe },
    { id: "telegram", label: "تيليجرام", icon: Send },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">سجل المحادثات</h1>
        <p className="text-sm text-slate-400 mt-1">
          راقب محادثات عملائك عبر الموقع وتيليجرام — وتدخّل يدوياً عند الحاجة.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-2xl overflow-x-auto shrink-0">
            {statusTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-2 rounded-xl text-sm font-semibold transition-all duration-200 whitespace-nowrap ${
                  activeTab === tab.id
                    ? "bg-slate-800 text-emerald-400 shadow-md"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:max-w-xs">
            <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-slate-500">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              placeholder="البحث بالمعرف أو الرقم..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-2xl py-2.5 pr-10 pl-4 text-slate-100 placeholder-slate-600 text-sm outline-none transition-all duration-200"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {channelTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setChannelFilter(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 border ${
                  channelFilter === tab.id
                    ? "bg-slate-800 text-slate-200 border-slate-700"
                    : "bg-transparent text-slate-500 border-slate-800 hover:text-slate-300 hover:border-slate-700"
                }`}
              >
                {Icon && <Icon className="w-3.5 h-3.5" />}
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
        {isLoading ? (
          <div className="py-24 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            <span className="text-sm text-slate-400">جاري تحميل المحادثات...</span>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="py-24 text-center">
            <MessageSquare className="w-12 h-12 text-slate-700 mx-auto mb-3 opacity-30" />
            <p className="font-bold text-slate-400">لا توجد محادثات مطابقة</p>
            <p className="text-xs text-slate-600 mt-1">
              {activeTab === "all" && channelFilter === "all"
                ? "لم يتحدث أي عميل مع الشات بوت بعد"
                : "لا توجد محادثات بهذا التصنيف"}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => navigate(`/dashboard/conversations/${conv.id}`)}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-900/50 cursor-pointer transition-all duration-200 group border-r-4 border-transparent hover:border-emerald-500"
              >
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 bg-slate-800 group-hover:bg-slate-700 rounded-2xl flex items-center justify-center border border-slate-700 transition-colors shrink-0">
                    {conv.channel === "telegram"
                      ? <Send className="w-5 h-5 text-sky-400" />
                      : <Globe className="w-5 h-5 text-blue-400" />
                    }
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-slate-200 group-hover:text-slate-100 transition-colors">
                        {getDisplayId(conv)}
                      </span>
                      {getChannelBadge(conv.channel)}
                      {getStatusBadge(conv.status)}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-600" />
                        {new Date(conv.started_at).toLocaleDateString("ar-EG")}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3.5 h-3.5 text-slate-600" />
                        {conv.message_count} رسالة
                      </span>
                      {conv.ai_mode ? (
                        <span className="flex items-center gap-1 text-emerald-500/80">
                          <Bot className="w-3.5 h-3.5" /> ذكاء اصطناعي
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-blue-400/80">
                          <User className="w-3.5 h-3.5" /> وكيل بشري
                        </span>
                      )}
                    </div>
                  </div>
                </div>

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
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-emerald-400 transition-all duration-200">
                    <ChevronLeft className="w-5 h-5" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {filteredConversations.length > 0 && (
        <p className="text-center text-xs text-slate-600">
          {filteredConversations.length} محادثة — يتجدد تلقائياً كل 10 ثوانٍ
        </p>
      )}
    </div>
  );
}
