import React from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLocation, Link } from "wouter";
import {
  FileText,
  MessageSquare,
  LogOut,
  Loader2,
  Settings,
  LayoutDashboard,
  UserCheck,
  Brain,
  Plug,
} from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const [pathname] = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
        <span className="text-slate-400 text-sm">جاري تحميل نصيح...</span>
      </div>
    );
  }

  if (!user) return null;

  const navItems = [
    { name: "الرئيسية", href: "/dashboard/overview", icon: LayoutDashboard },
    { name: "قاعدة المعرفة", href: "/dashboard/documents", icon: FileText },
    { name: "تحويلات الموظفين", href: "/dashboard/handoffs", icon: UserCheck },
    { name: "الأسئلة غير المجاب عنها", href: "/dashboard/conversations", icon: MessageSquare },
    { name: "التكامل والنشر", href: "/dashboard/integration", icon: Plug },
    { name: "إعدادات البوت", href: "/dashboard/settings", icon: Settings },
  ];

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden" dir="rtl">
      <aside className="w-72 bg-slate-900 border-l border-slate-800 flex flex-col z-20">
        <div className="p-6 border-b border-slate-800 flex items-center gap-3 shrink-0">
          <div className="w-10 h-10 bg-gradient-to-tr from-emerald-500 to-teal-400 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Brain className="w-5 h-5 text-slate-950 stroke-[2.5]" />
          </div>
          <div>
            <h2 className="font-extrabold text-slate-100 text-lg leading-none tracking-tight">نصيح</h2>
            <span className="text-[10px] text-slate-500 mt-1 block">وكيل دعم العملاء الذكي</span>
          </div>
        </div>

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
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? "text-emerald-400" : "text-slate-500 group-hover:text-slate-300"}`} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800">
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-all duration-200 text-sm font-medium group"
          >
            <LogOut className="w-5 h-5 shrink-0 text-slate-500 group-hover:text-red-400" />
            <span>تسجيل الخروج</span>
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-slate-950">
        {children}
      </main>
    </div>
  );
}
