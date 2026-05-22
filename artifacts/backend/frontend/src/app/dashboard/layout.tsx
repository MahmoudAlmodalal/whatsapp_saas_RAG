"use client";

import React from "react";
import { useAuth } from "@/components/AuthProvider";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { 
  FileText, 
  MessageSquare, 
  UserCheck, 
  LogOut, 
  Loader2, 
  Building2,
  Settings
} from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
        <span className="text-slate-400 text-sm">جاري تحميل لوحة التحكم...</span>
      </div>
    );
  }

  // If no user is logged in, hide content (AuthProvider handles redirection)
  if (!user) {
    return null;
  }

  const navItems = [
    {
      name: "المحادثات",
      href: "/dashboard/conversations",
      icon: MessageSquare,
    },
    {
      name: "قائمة الانتظار (الهاندوف)",
      href: "/dashboard/handoffs",
      icon: UserCheck,
    },
    {
      name: "قاعدة المعرفة (المستندات)",
      href: "/dashboard/documents",
      icon: FileText,
    },
    {
      name: "الإعدادات",
      href: "/dashboard/settings",
      icon: Settings,
    },
  ];

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case "admin":
        return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
      case "agent":
        return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
      default:
        return "bg-slate-500/10 text-slate-400 border border-slate-500/20";
    }
  };

  const getRoleName = (role: string) => {
    switch (role) {
      case "admin":
        return "مدير النظام";
      case "agent":
        return "عميل خدمة";
      default:
        return role;
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden">
      {/* Sidebar - fixed on the right for RTL layout */}
      <aside className="w-72 bg-slate-900 border-l border-slate-800 flex flex-col z-20">
        {/* Brand Logo */}
        <div className="p-6 border-b border-slate-800 flex items-center gap-3 shrink-0">
          <div className="w-10 h-10 bg-gradient-to-tr from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/10">
            <MessageSquare className="w-5 h-5 text-slate-950 stroke-[2.5]" />
          </div>
          <div>
            <h2 className="font-extrabold text-slate-100 text-base leading-none">منصة واتساب الذكية</h2>
            <span className="text-[10px] text-slate-500 mt-1 block">نظام خدمة العملاء الآلي</span>
          </div>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3.5 px-4 py-3.5 rounded-xl font-medium text-sm transition-all duration-200 group ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400 border-r-4 border-emerald-500"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-105 ${
                  isActive ? "text-emerald-400" : "text-slate-500 group-hover:text-slate-400"
                }`} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Info & Logout Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50 shrink-0">
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 mb-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">الدور</span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${getRoleBadgeColor(user.role)}`}>
                {getRoleName(user.role)}
              </span>
            </div>
            <div className="flex items-start gap-2 text-xs text-slate-400">
              <Building2 className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
              <div className="truncate">
                <span className="text-[10px] text-slate-500 block leading-none">معرف الشريك</span>
                <span className="font-mono text-[10px]">{user.tenant_id}</span>
              </div>
            </div>
          </div>
          
          <button
            onClick={() => logout()}
            className="w-full py-3 px-4 bg-slate-800 hover:bg-rose-500/10 hover:text-rose-400 text-slate-300 font-bold text-sm rounded-xl flex items-center justify-center gap-2 border border-slate-700 hover:border-rose-500/20 transition-all duration-200"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            <span>تسجيل الخروج</span>
          </button>
        </div>
      </aside>

      {/* Main content viewport */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Background ambient lighting */}
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-emerald-500/[0.02] rounded-full blur-3xl -z-10 pointer-events-none" />
        <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-blue-500/[0.02] rounded-full blur-3xl -z-10 pointer-events-none" />
        
        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-8 relative">
          {children}
        </div>
      </main>
    </div>
  );
}
