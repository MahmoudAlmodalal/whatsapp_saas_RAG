import React, { createContext, useContext, useState, useEffect } from "react";
import { useLocation } from "wouter";

interface SuperAdmin {
  id: string;
  email: string;
  role: string;
}

interface SuperAdminContextType {
  admin: SuperAdmin | null;
  loading: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SuperAdminContext = createContext<SuperAdminContextType | undefined>(undefined);

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export function SuperAdminProvider({ children }: { children: React.ReactNode }) {
  const [admin, setAdmin] = useState<SuperAdmin | null>(null);
  const [loading, setLoading] = useState(true);
  const [, navigate] = useLocation();

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/super-admin/me`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setAdmin(data.admin);
      } else {
        setAdmin(null);
      }
    } catch {
      setAdmin(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const logout = async () => {
    try {
      await fetch(`${BASE}/api/super-admin/logout`, { method: "POST", credentials: "include" });
    } catch { /* ignore */ } finally {
      setAdmin(null);
      navigate("/login");
    }
  };

  return (
    <SuperAdminContext.Provider value={{ admin, loading, logout, refresh }}>
      {children}
    </SuperAdminContext.Provider>
  );
}

export function useSuperAdmin() {
  const ctx = useContext(SuperAdminContext);
  if (!ctx) throw new Error("useSuperAdmin must be used within SuperAdminProvider");
  return ctx;
}
