import React from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  MessageSquare,
  FileText,
  TrendingUp,
  Zap,
  Crown,
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  Loader2,
  BarChart3,
  Users,
  Clock
} from "lucide-react";
import { Link } from "wouter";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const PLAN_LIMITS: Record<string, { label: string; msgs: number; color: string; gradient: string }> = {
  free:     { label: "مجاني",   msgs: 50,    color: "text-slate-400",  gradient: "from-slate-500 to-slate-600" },
  starter:  { label: "Starter", msgs: 500,   color: "text-blue-400",   gradient: "from-blue-500 to-blue-600" },
  pro:      { label: "Pro",     msgs: 2000,  color: "text-emerald-400", gradient: "from-emerald-500 to-teal-600" },
  business: { label: "Business",msgs: 99999, color: "text-amber-400",  gradient: "from-amber-500 to-orange-500" },
};

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "text-emerald-400",
  iconBg = "bg-emerald-500/10",
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  iconBg?: string;
}) {
  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition-all duration-200">
      <div className="flex items-start justify-between gap-3">
        <div className={`w-10 h-10 ${iconBg} rounded-xl flex items-center justify-center shrink-0`}>
          <Icon className={`w-5 h-5 ${color}`} />
        </div>
        <div className="text-left flex-1 min-w-0">
          <p className="text-xs text-slate-500 mb-1 truncate">{label}</p>
          <p className={`text-2xl font-extrabold ${color} leading-none`}>{value}</p>
          {sub && <p className="text-[11px] text-slate-600 mt-1.5">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const { user } = useAuth();
  const tenantId = user?.tenant_id;

  const { data: tenant, isLoading } = useQuery<any>({
    queryKey: ["tenantOverview", tenantId],
    queryFn: async () => {
      if (!tenantId) throw new Error("no tenant");
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}`);
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    enabled: !!tenantId,
  });

  const { data: convStats } = useQuery<any>({
    queryKey: ["convStats", tenantId],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/conversations?tenant_id=${tenantId}&limit=1`);
      if (!res.ok) return { total: 0 };
      return res.json();
    },
    enabled: !!tenantId,
  });

  const { data: docs } = useQuery<any[]>({
    queryKey: ["docsOverview", tenantId],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/documents?tenant_id=${tenantId}`);
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!tenantId,
  });

  const tier = (tenant?.subscription_tier || "free") as string;
  const plan = PLAN_LIMITS[tier] || PLAN_LIMITS.free;
  const msgsUsed = tenant?.messages_used_this_month ?? 0;
  const msgsLimit = plan.msgs;
  const usagePercent = msgsLimit >= 99999 ? 100 : Math.min(100, Math.round((msgsUsed / msgsLimit) * 100));
  const docsCount = docs?.length ?? 0;
  const docsReady = docs?.filter((d: any) => d.status === "ready").length ?? 0;
  const totalConvs = convStats?.total ?? 0;

  const isConfigured = !!(tenant?.config?.ai_persona_name);
  const hasDocuments = docsCount > 0;

  const steps = [
    { label: "رفع مستند واحد على الأقل", done: hasDocuments, href: "/dashboard/documents" },
    { label: "ضبط إعدادات الشات بوت", done: isConfigured, href: "/dashboard/settings" },
    { label: "نسخ كود التضمين ونشره", done: false, href: "/dashboard/integration" },
  ];
  const setupDone = steps.every(s => s.done);

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
        <span className="text-sm text-slate-400">جاري تحميل البيانات...</span>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-emerald-500" />
            <span>لوحة التحكم</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            مرحباً — إليك ملخص حساب <span className="text-slate-300 font-semibold">{tenant?.name || "شركتك"}</span>
          </p>
        </div>

        <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border bg-gradient-to-l ${plan.gradient} bg-opacity-10 border-slate-700`}>
          <Crown className={`w-4 h-4 ${plan.color}`} />
          <span className={`text-sm font-bold ${plan.color}`}>باقة {plan.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={MessageSquare}
          label="المحادثات هذا الشهر"
          value={msgsUsed}
          sub={msgsLimit >= 99999 ? "غير محدود" : `من أصل ${msgsLimit.toLocaleString()}`}
          color="text-emerald-400"
          iconBg="bg-emerald-500/10"
        />
        <StatCard
          icon={FileText}
          label="المستندات المرفوعة"
          value={docsCount}
          sub={docsReady > 0 ? `${docsReady} جاهز للاستخدام` : "لا توجد مستندات جاهزة بعد"}
          color="text-blue-400"
          iconBg="bg-blue-500/10"
        />
        <StatCard
          icon={Users}
          label="إجمالي المحادثات"
          value={totalConvs}
          sub="منذ بداية الاشتراك"
          color="text-violet-400"
          iconBg="bg-violet-500/10"
        />
        <StatCard
          icon={Zap}
          label="حالة الشات بوت"
          value={isConfigured && hasDocuments ? "نشط" : "غير مكتمل"}
          sub={isConfigured && hasDocuments ? "يرد على العملاء الآن" : "أكمل الإعداد أدناه"}
          color={isConfigured && hasDocuments ? "text-emerald-400" : "text-amber-400"}
          iconBg={isConfigured && hasDocuments ? "bg-emerald-500/10" : "bg-amber-500/10"}
        />
      </div>

      {!setupDone && (
        <div className="bg-slate-900/60 backdrop-blur-xl border border-amber-500/20 rounded-3xl p-6 space-y-4">
          <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            <span>أكمل إعداد الشات بوت</span>
          </h2>
          <p className="text-sm text-slate-400">اتبع الخطوات التالية لتفعيل شات بوتك وبدء الرد على العملاء:</p>
          <div className="space-y-3">
            {steps.map((step, i) => (
              <Link key={i} href={step.href}>
                <div className={`flex items-center gap-3 p-4 rounded-2xl border transition-all duration-200 cursor-pointer ${
                  step.done
                    ? "bg-emerald-500/5 border-emerald-500/20 opacity-60"
                    : "bg-slate-950/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/80"
                }`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                    step.done ? "bg-emerald-500/20" : "bg-slate-800"
                  }`}>
                    {step.done
                      ? <CheckCircle className="w-4 h-4 text-emerald-400" />
                      : <span className="text-xs font-bold text-slate-500">{i + 1}</span>
                    }
                  </div>
                  <span className={`flex-1 text-sm font-medium ${step.done ? "text-slate-500 line-through" : "text-slate-300"}`}>
                    {step.label}
                  </span>
                  {!step.done && <ArrowLeft className="w-4 h-4 text-slate-600 shrink-0" />}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {setupDone && (
        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-3xl p-6 flex items-start gap-4">
          <CheckCircle className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-emerald-400">الشات بوت جاهز ونشط!</p>
            <p className="text-xs text-slate-400 mt-1">
              بوتك يرد على العملاء تلقائياً. يمكنك مراجعة المحادثات أو تحديث قاعدة المعرفة في أي وقت.
            </p>
          </div>
        </div>
      )}

      {msgsLimit < 99999 && (
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-500" />
              <span>استخدام الباقة هذا الشهر</span>
            </h2>
            <span className="text-sm text-slate-400 font-mono">
              {msgsUsed.toLocaleString()} / {msgsLimit.toLocaleString()}
            </span>
          </div>

          <div className="relative h-3 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                usagePercent >= 90 ? "bg-rose-500" :
                usagePercent >= 70 ? "bg-amber-500" :
                "bg-gradient-to-l from-emerald-500 to-teal-500"
              }`}
              style={{ width: `${usagePercent}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>{usagePercent}% مستخدم</span>
            {usagePercent >= 80 && (
              <span className="flex items-center gap-1.5 text-amber-400">
                <AlertCircle className="w-3.5 h-3.5" />
                اقتربت من الحد — فكر في ترقية الباقة
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            {[
              { name: "مجاني", price: "$0", msgs: "50 محادثة", tier: "free" },
              { name: "Starter", price: "$9", msgs: "500 محادثة", tier: "starter" },
              { name: "Pro", price: "$19", msgs: "2,000 محادثة", tier: "pro" },
              { name: "Business", price: "$39", msgs: "غير محدود", tier: "business" },
            ].map((p) => (
              <div
                key={p.tier}
                className={`p-3 rounded-2xl border text-right transition-all duration-200 ${
                  p.tier === tier
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-slate-950/40 border-slate-800 hover:border-slate-700"
                }`}
              >
                <p className={`text-xs font-bold ${p.tier === tier ? "text-emerald-400" : "text-slate-300"}`}>
                  {p.name}
                  {p.tier === tier && <span className="text-[9px] mr-1">✓ حاليًا</span>}
                </p>
                <p className="text-base font-extrabold text-slate-100 mt-0.5">{p.price}<span className="text-[10px] text-slate-500 font-normal">/شهر</span></p>
                <p className="text-[10px] text-slate-500 mt-0.5">{p.msgs}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link href="/dashboard/documents">
          <div className="group bg-slate-900/60 border border-slate-800 hover:border-emerald-500/30 rounded-2xl p-5 cursor-pointer transition-all duration-200 hover:bg-slate-900/80">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-9 h-9 bg-blue-500/10 rounded-xl flex items-center justify-center">
                <FileText className="w-5 h-5 text-blue-400" />
              </div>
              <span className="font-bold text-slate-200 text-sm">قاعدة المعرفة</span>
            </div>
            <p className="text-xs text-slate-500">ارفع ملفات PDF أو DOCX أو TXT وسيتعلم بوتك من محتواها تلقائياً.</p>
            <div className="flex items-center gap-1 text-emerald-500 text-xs mt-3 group-hover:gap-2 transition-all">
              <span>إدارة المستندات</span>
              <ArrowLeft className="w-3.5 h-3.5" />
            </div>
          </div>
        </Link>

        <Link href="/dashboard/integration">
          <div className="group bg-slate-900/60 border border-slate-800 hover:border-emerald-500/30 rounded-2xl p-5 cursor-pointer transition-all duration-200 hover:bg-slate-900/80">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-9 h-9 bg-violet-500/10 rounded-xl flex items-center justify-center">
                <Bot className="w-5 h-5 text-violet-400" />
              </div>
              <span className="font-bold text-slate-200 text-sm">نشر الشات بوت</span>
            </div>
            <p className="text-xs text-slate-500">انسخ كود التضمين على موقعك أو اربطه بـ Telegram في دقيقة واحدة.</p>
            <div className="flex items-center gap-1 text-emerald-500 text-xs mt-3 group-hover:gap-2 transition-all">
              <span>إعداد التكامل</span>
              <ArrowLeft className="w-3.5 h-3.5" />
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
