import React from "react";
import { useSuperAdmin } from "@/components/SuperAdminProvider";
import { useLocation, Link, Redirect } from "wouter";
import { Shield, Building2, Users, LogOut, Loader2, Settings, Bot } from "lucide-react";

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  const { admin, logout, refresh } = useSuperAdmin();
  const [pathname] = useLocation();
  const [checking, setChecking] = React.useState(true);

  React.useEffect(() => {
    refresh().finally(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center gap-3">
        <Loader2 className="w-10 h-10 text-violet-500 animate-spin" />
        <span className="text-slate-400 text-sm">جاري التحميل...</span>
      </div>
    );
  }

  if (!admin) return <Redirect to="/super-admin/login" />;

  const navItems = [
    { name: "الشركات", href: "/super-admin/dashboard/tenants", icon: Building2 },
    { name: "الحسابات", href: "/super-admin/dashboard/accounts", icon: Users },
    { name: "إعدادات النظام", href: "/super-admin/dashboard/settings", icon: Settings },
  ];

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden">
      <aside className="w-72 bg-slate-900 border-l border-slate-800 flex flex-col z-20">
        <div className="p-6 border-b border-slate-800 flex items-center gap-3 shrink-0">
          <div className="w-10 h-10 bg-gradient-to-tr from-violet-600 to-purple-700 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/20">
            <Shield className="w-5 h-5 text-white stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="font-extrabold text-slate-100 text-lg leading-none tracking-tight">رسن</h2>
              <span className="text-[9px] px-1.5 py-0.5 bg-violet-500/20 text-violet-400 rounded-md font-bold uppercase tracking-wider">Admin</span>
            </div>
            <span className="text-[10px] text-violet-400 mt-1 block">لوحة تحكم المشرف العام</span>
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
                    ? "bg-violet-500/10 text-violet-400 border-r-4 border-violet-500"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? "text-violet-400" : "text-slate-500 group-hover:text-slate-400"}`} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 shrink-0">
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-violet-600/20 flex items-center justify-center">
                <Shield className="w-3.5 h-3.5 text-violet-400" />
              </div>
              <div className="truncate">
                <p className="text-[10px] text-slate-500">مشرف عام</p>
                <p className="text-xs text-slate-300 font-mono truncate">{admin.email}</p>
              </div>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full py-3 px-4 bg-slate-800 hover:bg-rose-500/10 hover:text-rose-400 text-slate-300 font-bold text-sm rounded-xl flex items-center justify-center gap-2 border border-slate-700 hover:border-rose-500/20 transition-all duration-200"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            <span>تسجيل الخروج</span>
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
