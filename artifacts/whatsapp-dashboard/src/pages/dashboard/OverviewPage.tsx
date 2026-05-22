import React, { useMemo } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  MessageSquare,
  FileText,
  TrendingUp,
  TrendingDown,
  Zap,
  Crown,
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  BarChart3,
  Users,
  UserCheck,
  XCircle,
  RefreshCw,
} from "lucide-react";
import { Link } from "wouter";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const PLAN_LIMITS: Record<string, { label: string; msgs: number; color: string; gradient: string }> = {
  free:     { label: "مجاني",    msgs: 50,    color: "text-slate-400",   gradient: "from-slate-500 to-slate-600" },
  starter:  { label: "Starter",  msgs: 500,   color: "text-blue-400",    gradient: "from-blue-500 to-blue-600" },
  pro:      { label: "Pro",      msgs: 2000,  color: "text-emerald-400", gradient: "from-emerald-500 to-teal-600" },
  business: { label: "Business", msgs: 99999, color: "text-amber-400",   gradient: "from-amber-500 to-orange-500" },
  basic:    { label: "Basic",    msgs: 50,    color: "text-slate-400",   gradient: "from-slate-500 to-slate-600" },
  enterprise:{ label: "Enterprise", msgs: 99999, color: "text-amber-400", gradient: "from-amber-500 to-orange-500" },
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function currentMonthRange() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end   = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
  return { start, end };
}

function lastMonthRange() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const end   = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59);
  return { start, end };
}

function pct(a: number, b: number) {
  if (b === 0) return 0;
  return Math.round((a / b) * 100);
}

function trendLabel(curr: number, prev: number): { value: number; positive: boolean } | null {
  if (prev === 0) return null;
  const diff = Math.round(((curr - prev) / prev) * 100);
  return { value: Math.abs(diff), positive: diff >= 0 };
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 animate-pulse">
      <div className="flex items-start justify-between gap-3">
        <div className="w-10 h-10 bg-slate-800 rounded-xl shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-3 bg-slate-800 rounded w-2/3" />
          <div className="h-7 bg-slate-800 rounded w-1/2" />
          <div className="h-2.5 bg-slate-800 rounded w-3/4" />
        </div>
      </div>
    </div>
  );
}

// ── StatCard ─────────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "text-emerald-400",
  iconBg = "bg-emerald-500/10",
  trend,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  iconBg?: string;
  trend?: { value: number; positive: boolean } | null;
}) {
  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition-all duration-200">
      <div className="flex items-start justify-between gap-3">
        <div className={`w-10 h-10 ${iconBg} rounded-xl flex items-center justify-center shrink-0`}>
          <Icon className={`w-5 h-5 ${color}`} />
        </div>
        <div className="flex-1 min-w-0 text-end">
          <p className="text-xs text-slate-500 mb-1 truncate">{label}</p>
          <p className={`text-2xl font-extrabold ${color} leading-none`}>{value}</p>
          <div className="flex items-center justify-end gap-2 mt-1.5 flex-wrap">
            {sub && <p className="text-[11px] text-slate-600">{sub}</p>}
            {trend && (
              <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${trend.positive ? "text-emerald-400" : "text-rose-400"}`}>
                {trend.positive
                  ? <TrendingUp className="w-3 h-3" />
                  : <TrendingDown className="w-3 h-3" />}
                {trend.value}% عن الشهر الماضي
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Ring Gauge ────────────────────────────────────────────────────────────────

function RingGauge({ percent, limit, used }: { percent: number; limit: number; used: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const filled = circ * (percent / 100);
  const empty = circ - filled;

  const color =
    percent >= 90 ? "#f43f5e" :
    percent >= 70 ? "#f59e0b" :
    "#10b981";

  const label =
    percent >= 90 ? "خطر — قريب من الحد" :
    percent >= 70 ? "تنبيه — استخدام مرتفع" :
    "مستوى الاستخدام جيد";

  const labelColor =
    percent >= 90 ? "text-rose-400" :
    percent >= 70 ? "text-amber-400" :
    "text-emerald-400";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          {/* Track */}
          <circle
            cx="60" cy="60" r={r}
            fill="none"
            stroke="#1e293b"
            strokeWidth="12"
          />
          {/* Fill */}
          <circle
            cx="60" cy="60" r={r}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${empty}`}
            style={{ transition: "stroke-dasharray 0.8s ease" }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-extrabold text-slate-100">{percent}%</span>
          <span className="text-[10px] text-slate-500 mt-0.5">مستخدم</span>
        </div>
      </div>
      <div className="text-center space-y-0.5">
        <p className="text-sm font-mono text-slate-300">
          {used.toLocaleString()} / {limit.toLocaleString()}
        </p>
        <p className={`text-xs font-semibold ${labelColor}`}>{label}</p>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function OverviewPage() {
  const { user } = useAuth();
  const tenantId = user?.tenant_id;

  const queryOpts = { enabled: !!tenantId, staleTime: 60_000 };

  const tenantQuery = useQuery<any>({
    queryKey: ["tenantOverview", tenantId],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/tenants/${tenantId}`);
      if (!res.ok) throw new Error("failed");
      return res.json();
    },
    ...queryOpts,
  });

  const docsQuery = useQuery<any[]>({
    queryKey: ["docsOverview", tenantId],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/documents?tenant_id=${tenantId}`);
      if (!res.ok) return [];
      return res.json();
    },
    ...queryOpts,
  });

  // Fetch enough conversations to compute all stats + trends
  const convsQuery = useQuery<any[]>({
    queryKey: ["convsOverview", tenantId],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/conversations?tenant_id=${tenantId}&limit=2000`);
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : (data?.items ?? data?.conversations ?? []);
    },
    ...queryOpts,
  });

  // Derived stats
  const stats = useMemo(() => {
    const convs: any[] = convsQuery.data ?? [];
    const { start: thisStart } = currentMonthRange();
    const { start: lastStart, end: lastEnd } = lastMonthRange();

    const thisMonth = convs.filter(c => new Date(c.started_at) >= thisStart);
    const lastMonth = convs.filter(c => {
      const d = new Date(c.started_at);
      return d >= lastStart && d <= lastEnd;
    });

    const handoffCount = convs.filter(c => c.status === "handoff" || c.ai_mode === false).length;
    const closedCount  = convs.filter(c => c.status === "closed").length;
    const total = convs.length;

    const handoffRate = pct(handoffCount, total);
    const closeRate   = pct(closedCount, total);

    const thisMonthHandoff = thisMonth.filter(c => c.status === "handoff" || c.ai_mode === false).length;
    const lastMonthHandoff = lastMonth.filter(c => c.status === "handoff" || c.ai_mode === false).length;
    const handoffRateLast = pct(lastMonthHandoff, lastMonth.length);
    const handoffRateCurr = pct(thisMonthHandoff, thisMonth.length);

    return {
      total,
      thisMonthCount: thisMonth.length,
      lastMonthCount: lastMonth.length,
      handoffRate,
      closeRate,
      convTrend: trendLabel(thisMonth.length, lastMonth.length),
      handoffTrend: trendLabel(handoffRateCurr, handoffRateLast) 
        ? { value: trendLabel(handoffRateCurr, handoffRateLast)!.value, positive: !trendLabel(handoffRateCurr, handoffRateLast)!.positive }
        : null,
    };
  }, [convsQuery.data]);

  const tenant = tenantQuery.data;
  const docs = docsQuery.data ?? [];

  const tier = (tenant?.subscription_tier || "free") as string;
  const plan = PLAN_LIMITS[tier] || PLAN_LIMITS.free;
  const msgsUsed = tenant?.messages_used_this_month ?? 0;
  const msgsLimit = plan.msgs;
  const usagePercent = msgsLimit >= 99999 ? 0 : Math.min(100, Math.round((msgsUsed / msgsLimit) * 100));
  const docsCount = docs.length;
  const docsReady = docs.filter((d: any) => d.status === "ready").length;

  const isConfigured = !!(tenant?.config?.ai_persona_name);
  const hasDocuments = docsCount > 0;
  const setupDone = isConfigured && hasDocuments;

  const steps = [
    { label: "رفع مستند واحد على الأقل", done: hasDocuments, href: "/dashboard/documents" },
    { label: "ضبط إعدادات الشات بوت",   done: isConfigured, href: "/dashboard/settings" },
    { label: "نسخ كود التضمين ونشره",    done: false,        href: "/dashboard/integration" },
  ];

  // Last updated
  const updatedAt = tenantQuery.dataUpdatedAt;
  const updatedLabel = updatedAt
    ? new Intl.DateTimeFormat("ar-SA", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(updatedAt))
    : null;

  const isLoading = tenantQuery.isLoading;
  const isRefreshing = tenantQuery.isFetching || docsQuery.isFetching || convsQuery.isFetching;

  function refetchAll() {
    tenantQuery.refetch();
    docsQuery.refetch();
    convsQuery.refetch();
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-emerald-500" />
            <span>لوحة التحكم</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            مرحباً — إليك ملخص حساب{" "}
            <span className="text-slate-300 font-semibold">{tenant?.name || "شركتك"}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Last updated + refresh */}
          <div className="flex items-center gap-2">
            {updatedLabel && (
              <span className="text-[11px] text-slate-600">آخر تحديث: {updatedLabel}</span>
            )}
            <button
              onClick={refetchAll}
              disabled={isRefreshing}
              className="p-1.5 rounded-lg border border-slate-800 hover:border-slate-700 text-slate-500 hover:text-slate-300 transition-all disabled:opacity-40"
              title="تحديث"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* Plan badge */}
          <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border bg-gradient-to-l ${plan.gradient} bg-opacity-10 border-slate-700`}>
            <Crown className={`w-4 h-4 ${plan.color}`} />
            <span className={`text-sm font-bold ${plan.color}`}>باقة {plan.label}</span>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading || convsQuery.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              icon={MessageSquare}
              label="رسائل هذا الشهر"
              value={msgsUsed.toLocaleString()}
              sub={msgsLimit >= 99999 ? "غير محدود" : `من أصل ${msgsLimit.toLocaleString()}`}
              color="text-emerald-400"
              iconBg="bg-emerald-500/10"
              trend={stats.convTrend}
            />
            <StatCard
              icon={Users}
              label="إجمالي المحادثات"
              value={stats.total.toLocaleString()}
              sub={`${stats.thisMonthCount} هذا الشهر`}
              color="text-violet-400"
              iconBg="bg-violet-500/10"
              trend={stats.convTrend}
            />
            <StatCard
              icon={UserCheck}
              label="معدل تحويل للموظف"
              value={`${stats.handoffRate}%`}
              sub={`حالات ما قدر البوت يحلها`}
              color={stats.handoffRate >= 30 ? "text-rose-400" : "text-amber-400"}
              iconBg={stats.handoffRate >= 30 ? "bg-rose-500/10" : "bg-amber-500/10"}
              trend={stats.handoffTrend}
            />
            <StatCard
              icon={XCircle}
              label="معدل إغلاق المحادثات"
              value={`${stats.closeRate}%`}
              sub="محادثات وصلت لـ closed"
              color="text-blue-400"
              iconBg="bg-blue-500/10"
              trend={null}
            />
          </>
        )}
      </div>

      {/* Documents stat (separate row) */}
      {!isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatCard
            icon={FileText}
            label="المستندات المرفوعة"
            value={docsCount}
            sub={docsReady > 0 ? `${docsReady} جاهز للاستخدام` : "لا توجد مستندات جاهزة بعد"}
            color="text-blue-400"
            iconBg="bg-blue-500/10"
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
      )}

      {/* Setup checklist */}
      {!isLoading && !setupDone && (
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
                      : <span className="text-xs font-bold text-slate-500">{i + 1}</span>}
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

      {!isLoading && setupDone && (
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

      {/* Usage ring gauge + plans */}
      {!isLoading && msgsLimit < 99999 && (
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 space-y-6">
          <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-emerald-500" />
            <span>استخدام الباقة هذا الشهر</span>
          </h2>

          <div className="flex flex-col sm:flex-row items-center gap-8">
            {/* Ring gauge */}
            <div className="shrink-0">
              <RingGauge percent={usagePercent} limit={msgsLimit} used={msgsUsed} />
            </div>

            {/* Plans comparison */}
            <div className="flex-1 w-full">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { name: "مجاني",    price: "$0",  msgs: "50 رسالة",      tier: "free" },
                  { name: "Starter",  price: "$9",  msgs: "500 رسالة",     tier: "starter" },
                  { name: "Pro",      price: "$19", msgs: "2,000 رسالة",   tier: "pro" },
                  { name: "Business", price: "$39", msgs: "غير محدود",     tier: "business" },
                ].map((p) => (
                  <div
                    key={p.tier}
                    className={`p-3 rounded-2xl border text-end transition-all duration-200 ${
                      p.tier === tier || (tier === "basic" && p.tier === "free")
                        ? "bg-emerald-500/10 border-emerald-500/30"
                        : "bg-slate-950/40 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <p className={`text-xs font-bold ${p.tier === tier || (tier === "basic" && p.tier === "free") ? "text-emerald-400" : "text-slate-300"}`}>
                      {p.name}
                      {(p.tier === tier || (tier === "basic" && p.tier === "free")) && (
                        <span className="text-[9px] me-1">✓ حاليًا</span>
                      )}
                    </p>
                    <p className="text-base font-extrabold text-slate-100 mt-0.5">
                      {p.price}<span className="text-[10px] text-slate-500 font-normal">/شهر</span>
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{p.msgs}</p>
                  </div>
                ))}
              </div>

              {usagePercent >= 80 && (
                <p className="flex items-center gap-1.5 text-amber-400 text-xs font-semibold mt-3">
                  <AlertCircle className="w-3.5 h-3.5" />
                  اقتربت من الحد — فكر في ترقية الباقة
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Quick links */}
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
