import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2, Plus, Pencil, Trash2, X, Check, Loader2,
  AlertCircle, Crown, ToggleLeft, ToggleRight, MessageSquare, Bot
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface Tenant {
  id: string;
  name: string;
  email?: string;
  subscriptionTier: string;
  isActive: boolean;
  createdAt: string;
  messagesUsed?: number;
}

const TIER_LABELS: Record<string, string> = {
  free: "مجاني",
  starter: "Starter",
  pro: "Pro",
  business: "Business",
};
const TIER_LIMITS: Record<string, number | string> = {
  free: 50,
  starter: 500,
  pro: 2000,
  business: "∞",
};
const TIER_COLORS: Record<string, string> = {
  free:     "bg-slate-500/10 text-slate-400 border-slate-500/20",
  starter:  "bg-blue-500/10 text-blue-400 border-blue-500/20",
  pro:      "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  business: "bg-amber-500/10 text-amber-400 border-amber-500/20",
};

function TenantFormModal({ initial, onClose, onSave }: {
  initial?: Partial<Tenant>;
  onClose: () => void;
  onSave: (data: Partial<Tenant>) => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [subscriptionTier, setSubscriptionTier] = useState(initial?.subscriptionTier ?? "free");
  const [isActive, setIsActive] = useState(initial?.isActive ?? true);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-100">{initial?.id ? "تعديل الشركة" : "إضافة شركة جديدة"}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">اسم الشركة *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="اسم الشركة أو المؤسسة"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 text-sm"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">البريد الإلكتروني</label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@company.com"
              type="email"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 text-sm"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">الباقة</label>
            <select
              value={subscriptionTier}
              onChange={(e) => setSubscriptionTier(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-violet-500 text-sm"
            >
              <option value="free">مجاني — 50 محادثة/شهر</option>
              <option value="starter">Starter — 500 محادثة/شهر ($9)</option>
              <option value="pro">Pro — 2,000 محادثة/شهر ($19)</option>
              <option value="business">Business — غير محدود ($39)</option>
            </select>
          </div>
          <div className="flex items-center justify-between">
            <label className="text-sm text-slate-400">الحالة</label>
            <button
              type="button"
              onClick={() => setIsActive(!isActive)}
              className={`flex items-center gap-2 text-sm font-medium transition-colors ${isActive ? "text-emerald-400" : "text-slate-500"}`}
            >
              {isActive ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
              {isActive ? "نشط" : "معطل"}
            </button>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => onSave({ name, email: email || undefined, subscriptionTier, isActive })}
            disabled={!name.trim()}
            className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-bold py-2.5 rounded-xl text-sm transition-all flex items-center justify-center gap-2"
          >
            <Check className="w-4 h-4" />
            {initial?.id ? "حفظ التعديلات" : "إضافة الشركة"}
          </button>
          <button onClick={onClose} className="px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium py-2.5 rounded-xl text-sm transition-all">
            إلغاء
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TenantsPage() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: tenants = [], isLoading, error } = useQuery<Tenant[]>({
    queryKey: ["super-admin-tenants"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/super-admin/tenants`, { credentials: "include" });
      if (!res.ok) throw new Error("فشل في تحميل البيانات");
      return res.json();
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: Partial<Tenant>) => {
      const res = await fetch(`${BASE}/api/super-admin/tenants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("فشل في الإضافة");
      return res.json();
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["super-admin-tenants"] }); setShowAdd(false); },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, ...data }: Partial<Tenant> & { id: string }) => {
      const res = await fetch(`${BASE}/api/super-admin/tenants/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("فشل في التعديل");
      return res.json();
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["super-admin-tenants"] }); setEditingTenant(null); },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${BASE}/api/super-admin/tenants/${id}`, {
        method: "DELETE", credentials: "include",
      });
      if (!res.ok) throw new Error("فشل في الحذف");
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["super-admin-tenants"] }); setDeletingId(null); },
  });

  const tierCounts = tenants.reduce((acc, t) => {
    acc[t.subscriptionTier] = (acc[t.subscriptionTier] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            <Building2 className="w-6 h-6 text-violet-400" />
            إدارة الشركات
          </h1>
          <p className="text-slate-500 text-sm mt-1">جميع الشركات المشتركة في منصة رسن</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-bold px-4 py-2.5 rounded-xl text-sm transition-all shadow-lg shadow-violet-500/10"
        >
          <Plus className="w-4 h-4" />
          إضافة شركة
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {["free", "starter", "pro", "business"].map((tier) => (
          <div key={tier} className={`p-4 rounded-2xl border ${TIER_COLORS[tier]} bg-opacity-5`}>
            <p className="text-xs font-bold">{TIER_LABELS[tier]}</p>
            <p className="text-2xl font-extrabold mt-1 text-slate-100">{tierCounts[tier] || 0}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">{TIER_LIMITS[tier]} محادثة/شهر</p>
          </div>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-xl p-4 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>فشل في تحميل البيانات</span>
        </div>
      )}

      {!isLoading && tenants.length === 0 && (
        <div className="text-center py-20 text-slate-500">
          <Bot className="w-12 h-12 mx-auto mb-3 opacity-20" />
          <p>لا توجد شركات بعد</p>
          <p className="text-xs mt-1">اضغط "إضافة شركة" لإنشاء أول عميل</p>
        </div>
      )}

      <div className="grid gap-4">
        {tenants.map((tenant) => (
          <div key={tenant.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition-all">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h3 className="font-bold text-slate-100 text-base">{tenant.name}</h3>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${TIER_COLORS[tenant.subscriptionTier] || TIER_COLORS.free}`}>
                    {TIER_LABELS[tenant.subscriptionTier] || tenant.subscriptionTier}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${tenant.isActive ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-slate-500/10 text-slate-500 border-slate-600/20"}`}>
                    {tenant.isActive ? "نشط" : "معطل"}
                  </span>
                </div>
                <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                  {tenant.email && (
                    <span className="font-mono">{tenant.email}</span>
                  )}
                  {tenant.messagesUsed !== undefined && (
                    <span className="flex items-center gap-1">
                      <MessageSquare className="w-3 h-3" />
                      {tenant.messagesUsed.toLocaleString()} محادثة هذا الشهر
                    </span>
                  )}
                  <span className="font-mono text-[10px] text-slate-600 truncate max-w-[120px]">{tenant.id}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setEditingTenant(tenant)}
                  className="p-2 text-slate-500 hover:text-violet-400 hover:bg-violet-500/10 rounded-lg transition-all"
                  title="تعديل"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                {deletingId === tenant.id ? (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => deleteMutation.mutate(tenant.id)}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all"
                    >
                      {deleteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    </button>
                    <button onClick={() => setDeletingId(null)} className="p-2 text-slate-500 hover:text-slate-300 rounded-lg transition-all">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeletingId(tenant.id)}
                    className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all"
                    title="حذف"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {showAdd && (
        <TenantFormModal
          onClose={() => setShowAdd(false)}
          onSave={(data) => createMutation.mutate(data)}
        />
      )}
      {editingTenant && (
        <TenantFormModal
          initial={editingTenant}
          onClose={() => setEditingTenant(null)}
          onSave={(data) => updateMutation.mutate({ id: editingTenant.id, ...data })}
        />
      )}
    </div>
  );
}
