import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users, Plus, Pencil, Trash2, X, Check, Loader2,
  AlertCircle, Building2, UserCheck, UserX, Eye, EyeOff
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface Tenant { id: string; name: string; }
interface TenantUser {
  id: string;
  tenantId: string;
  email: string;
  name: string;
  role: string;
  isActive: boolean;
  createdAt: string;
}

const ROLE_LABELS: Record<string, string> = { admin: "مدير", agent: "عميل خدمة" };
const ROLE_COLORS: Record<string, string> = {
  admin: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  agent: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

function UserFormModal({ tenantId, initial, onClose, onSave }: {
  tenantId: string;
  initial?: Partial<TenantUser>;
  onClose: () => void;
  onSave: (data: Partial<TenantUser> & { password?: string }) => void;
}) {
  const [email, setEmail] = useState(initial?.email ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [role, setRole] = useState(initial?.role ?? "agent");
  const [isActive, setIsActive] = useState(initial?.isActive ?? true);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const isEdit = !!initial?.id;
  const canSubmit = isEdit ? true : (email.trim() !== "" && password.trim() !== "");

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-100">{isEdit ? "تعديل الحساب" : "إضافة حساب جديد"}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-4">
          {!isEdit && (
            <div>
              <label className="text-sm text-slate-400 mb-1.5 block">البريد الإلكتروني *</label>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                type="email"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 text-sm"
              />
            </div>
          )}
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">الاسم</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="الاسم الكامل"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 text-sm"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">الدور</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-violet-500 text-sm"
            >
              <option value="agent">عميل خدمة (Agent)</option>
              <option value="admin">مدير (Admin)</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">
              {isEdit ? "تغيير كلمة المرور (اتركها فارغة للإبقاء على الحالية)" : "كلمة المرور *"}
            </label>
            <div className="relative">
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isEdit ? "••••••••" : "أدخل كلمة المرور"}
                type={showPassword ? "text" : "password"}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 text-sm pl-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          {isEdit && (
            <div className="flex items-center justify-between">
              <label className="text-sm text-slate-400">الحالة</label>
              <button
                onClick={() => setIsActive(!isActive)}
                className={`flex items-center gap-2 text-sm font-medium transition-colors ${isActive ? "text-emerald-400" : "text-slate-500"}`}
              >
                {isActive ? <UserCheck className="w-5 h-5" /> : <UserX className="w-5 h-5" />}
                {isActive ? "نشط" : "معطل"}
              </button>
            </div>
          )}
        </div>
        <div className="flex gap-3 pt-2">
          <button
            onClick={() => onSave({ email, name, role, isActive, ...(password.trim() && { password }) })}
            disabled={!canSubmit}
            className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-bold py-2.5 rounded-xl text-sm transition-all flex items-center justify-center gap-2"
          >
            <Check className="w-4 h-4" />
            {isEdit ? "حفظ التعديلات" : "إضافة"}
          </button>
          <button onClick={onClose} className="px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium py-2.5 rounded-xl text-sm transition-all">
            إلغاء
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [editingUser, setEditingUser] = useState<TenantUser | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: tenants = [], isLoading: loadingTenants } = useQuery<Tenant[]>({
    queryKey: ["super-admin-tenants"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/super-admin/tenants`, { credentials: "include" });
      if (!res.ok) throw new Error("فشل");
      return res.json();
    },
  });

  const { data: users = [], isLoading: loadingUsers } = useQuery<TenantUser[]>({
    queryKey: ["super-admin-users", selectedTenantId],
    enabled: !!selectedTenantId,
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/super-admin/tenants/${selectedTenantId}/users`, { credentials: "include" });
      if (!res.ok) throw new Error("فشل");
      return res.json();
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: Partial<TenantUser> & { password?: string }) => {
      const res = await fetch(`${BASE}/api/super-admin/tenants/${selectedTenantId}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل إنشاء الحساب");
      }
      return res.json();
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["super-admin-users", selectedTenantId] }); setShowAdd(false); },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, ...data }: Partial<TenantUser> & { id: string; password?: string }) => {
      const res = await fetch(`${BASE}/api/super-admin/users/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "فشل تحديث الحساب");
      }
      return res.json();
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["super-admin-users", selectedTenantId] }); setEditingUser(null); },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${BASE}/api/super-admin/users/${id}`, { method: "DELETE", credentials: "include" });
      if (!res.ok) throw new Error("فشل");
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["super-admin-users", selectedTenantId] }); setDeletingId(null); },
  });

  const selectedTenant = tenants.find((t) => t.id === selectedTenantId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          <Users className="w-6 h-6 text-violet-400" />
          إدارة الحسابات
        </h1>
        <p className="text-slate-500 text-sm mt-1">عرض وإدارة حسابات المستخدمين لكل شريك</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
        <label className="text-sm text-slate-400 mb-2 block flex items-center gap-2">
          <Building2 className="w-4 h-4" /> اختر الشريك
        </label>
        {loadingTenants ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm py-2">
            <Loader2 className="w-4 h-4 animate-spin" /> جاري التحميل...
          </div>
        ) : tenants.length === 0 ? (
          <p className="text-slate-600 text-sm py-2">لا يوجد شركاء — أضف شريكاً من صفحة الشركاء أولاً</p>
        ) : (
          <select
            value={selectedTenantId ?? ""}
            onChange={(e) => setSelectedTenantId(e.target.value || null)}
            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-violet-500 text-sm"
          >
            <option value="">-- اختر شريكاً --</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        )}
      </div>

      {selectedTenantId && (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-200">
              حسابات: <span className="text-violet-400">{selectedTenant?.name}</span>
            </h2>
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-bold px-4 py-2 rounded-xl text-sm transition-all"
            >
              <Plus className="w-4 h-4" /> إضافة حساب
            </button>
          </div>

          {loadingUsers && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
            </div>
          )}

          {!loadingUsers && users.length === 0 && (
            <div className="text-center py-16 text-slate-500">
              <Users className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>لا توجد حسابات لهذا الشريك</p>
            </div>
          )}

          <div className="grid gap-3">
            {users.map((user) => (
              <div key={user.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 hover:border-slate-700 transition-all">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-slate-200 text-sm">{user.name || "(بدون اسم)"}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${ROLE_COLORS[user.role] || "bg-slate-500/10 text-slate-400 border-slate-500/20"}`}>
                      {ROLE_LABELS[user.role] || user.role}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${user.isActive ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-slate-500/10 text-slate-500 border-slate-600/20"}`}>
                      {user.isActive ? "نشط" : "معطل"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1 font-mono">{user.email}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => setEditingUser(user)} className="p-2 text-slate-500 hover:text-violet-400 hover:bg-violet-500/10 rounded-lg transition-all">
                    <Pencil className="w-4 h-4" />
                  </button>
                  {deletingId === user.id ? (
                    <div className="flex items-center gap-1">
                      <button onClick={() => deleteMutation.mutate(user.id)} disabled={deleteMutation.isPending} className="p-2 text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all">
                        {deleteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                      </button>
                      <button onClick={() => setDeletingId(null)} className="p-2 text-slate-500 hover:text-slate-300 rounded-lg transition-all">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <button onClick={() => setDeletingId(user.id)} className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {showAdd && selectedTenantId && (
        <UserFormModal
          tenantId={selectedTenantId}
          onClose={() => setShowAdd(false)}
          onSave={(data) => createMutation.mutate(data)}
        />
      )}
      {editingUser && selectedTenantId && (
        <UserFormModal
          tenantId={selectedTenantId}
          initial={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={(data) => updateMutation.mutate({ id: editingUser.id, ...data })}
        />
      )}
    </div>
  );
}
