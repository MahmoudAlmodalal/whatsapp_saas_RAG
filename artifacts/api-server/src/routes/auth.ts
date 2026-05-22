import { Router } from "express";
import type { Request, Response } from "express";
import { decodeToken, isTokenExpired, refreshAccessToken } from "../lib/auth";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { db, superAdminsTable, tenantUsersTable } from "@workspace/db";
import { eq, and } from "drizzle-orm";

const router = Router();

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8001/api/v1";
const SUPER_ADMIN_JWT_SECRET = process.env.SUPER_ADMIN_JWT_SECRET || "super-admin-dev-secret-change-in-prod";
const JWT_SECRET = process.env.JWT_SECRET || "tenant-user-dev-secret-change-in-prod";

router.post("/auth/login", async (req: Request, res: Response) => {
  try {
    const { email, password } = req.body;
    const normalizedEmail = (email || "").toLowerCase();

    // 1. Check super admins
    const [superAdmin] = await db.select().from(superAdminsTable).where(eq(superAdminsTable.email, normalizedEmail)).limit(1);
    if (superAdmin) {
      const valid = await bcrypt.compare(password, superAdmin.passwordHash);
      if (!valid) return res.status(401).json({ detail: "البريد الإلكتروني أو كلمة المرور غير صحيحة" });
      const token = jwt.sign(
        { sub: superAdmin.id, email: superAdmin.email, role: "super_admin", tenant_id: null },
        SUPER_ADMIN_JWT_SECRET,
        { expiresIn: "8h" }
      );
      const isProdSA = process.env.NODE_ENV === "production";
      res.cookie("super_admin_token", token, {
        httpOnly: true, secure: isProdSA, sameSite: "strict", path: "/", maxAge: 8 * 3600 * 1000,
      });
      return res.json({ success: true, superAdmin: true, user: { id: superAdmin.id, email: superAdmin.email, role: "super_admin", tenant_id: null } });
    }

    // 2. Check tenant users in local DB
    const [tenantUser] = await db.select().from(tenantUsersTable).where(eq(tenantUsersTable.email, normalizedEmail)).limit(1);
    if (tenantUser) {
      if (!tenantUser.isActive) {
        return res.status(401).json({ detail: "هذا الحساب معطل. يرجى التواصل مع المسؤول." });
      }
      if (!tenantUser.passwordHash) {
        return res.status(401).json({ detail: "كلمة المرور غير مضبوطة لهذا الحساب." });
      }
      const valid = await bcrypt.compare(password, tenantUser.passwordHash);
      if (!valid) return res.status(401).json({ detail: "البريد الإلكتروني أو كلمة المرور غير صحيحة" });

      const isProd = process.env.NODE_ENV === "production";
      const accessToken = jwt.sign(
        { sub: tenantUser.id, email: tenantUser.email, role: tenantUser.role, tenant_id: tenantUser.tenantId },
        JWT_SECRET,
        { expiresIn: "1h" }
      );
      const refreshToken = jwt.sign(
        { sub: tenantUser.id, tenant_id: tenantUser.tenantId, type: "refresh" },
        JWT_SECRET,
        { expiresIn: "7d" }
      );

      res.cookie("access_token", accessToken, {
        httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 3600 * 1000,
      });
      res.cookie("refresh_token", refreshToken, {
        httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 7 * 24 * 3600 * 1000,
      });

      return res.json({
        success: true,
        user: { id: tenantUser.id, email: tenantUser.email, role: tenantUser.role, tenant_id: tenantUser.tenantId },
      });
    }

    // 3. Fall through to Python backend (if running)
    try {
      const response = await fetch(`${BACKEND_API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "فشل تسجيل الدخول" }));
        return res.status(response.status).json({ detail: errorData.detail || "البريد الإلكتروني أو كلمة المرور غير صحيحة" });
      }

      const tokenData = await response.json();
      let user = null;
      let isSuperAdmin = false;
      try {
        const decoded = decodeToken(tokenData.access_token);
        if (decoded) {
          user = { id: decoded.sub, tenant_id: decoded.tenant_id, role: decoded.role, email };
          isSuperAdmin = decoded.role === "super_admin";
        }
      } catch (e) {
        req.log.error({ err: e }, "Error decoding access token");
      }

      const isProd = process.env.NODE_ENV === "production";
      res.cookie("access_token", tokenData.access_token, {
        httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 3600 * 1000,
      });
      if (tokenData.refresh_token) {
        res.cookie("refresh_token", tokenData.refresh_token, {
          httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 7 * 24 * 3600 * 1000,
        });
      }
      if (isSuperAdmin) {
        const superAdminToken = jwt.sign(
          { sub: user!.id, email, role: "super_admin", tenant_id: null },
          SUPER_ADMIN_JWT_SECRET,
          { expiresIn: "8h" }
        );
        res.cookie("super_admin_token", superAdminToken, {
          httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 8 * 3600 * 1000,
        });
        return res.json({ success: true, superAdmin: true, user });
      }
      return res.json({ success: true, user });
    } catch {
      // Python backend not available — user not found locally either
      return res.status(401).json({ detail: "البريد الإلكتروني أو كلمة المرور غير صحيحة" });
    }
  } catch (error) {
    req.log.error({ err: error }, "Login proxy error");
    return res.status(500).json({ detail: "حدث خطأ أثناء الاتصال بالخادم. يرجى المحاولة لاحقاً." });
  }
});

router.post("/auth/logout", (req: Request, res: Response) => {
  res.clearCookie("access_token", { path: "/" });
  res.clearCookie("refresh_token", { path: "/" });
  return res.json({ success: true });
});

router.get("/auth/me", async (req: Request, res: Response) => {
  let accessToken = req.cookies?.access_token;
  const refreshToken = req.cookies?.refresh_token;
  const isProd = process.env.NODE_ENV === "production";

  if (!accessToken || isTokenExpired(accessToken)) {
    if (refreshToken) {
      // Try to refresh locally first
      try {
        const decoded = decodeToken(refreshToken);
        if (decoded && decoded.sub) {
          const [tenantUser] = await db.select().from(tenantUsersTable).where(
            and(eq(tenantUsersTable.id, decoded.sub), eq(tenantUsersTable.isActive, true))
          ).limit(1);
          if (tenantUser) {
            const newAccessToken = jwt.sign(
              { sub: tenantUser.id, email: tenantUser.email, role: tenantUser.role, tenant_id: tenantUser.tenantId },
              JWT_SECRET,
              { expiresIn: "1h" }
            );
            accessToken = newAccessToken;
            res.cookie("access_token", newAccessToken, {
              httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 3600 * 1000,
            });
          } else {
            // Try Python backend refresh
            const newAccessToken = await refreshAccessToken(BACKEND_API_URL, refreshToken);
            if (newAccessToken) {
              accessToken = newAccessToken;
              res.cookie("access_token", newAccessToken, {
                httpOnly: true, secure: isProd, sameSite: "strict", path: "/", maxAge: 3600 * 1000,
              });
            } else {
              res.clearCookie("access_token", { path: "/" });
              res.clearCookie("refresh_token", { path: "/" });
              return res.status(401).json({ detail: "غير مصرح" });
            }
          }
        }
      } catch {
        res.clearCookie("access_token", { path: "/" });
        res.clearCookie("refresh_token", { path: "/" });
        return res.status(401).json({ detail: "غير مصرح" });
      }
    } else {
      return res.status(401).json({ authenticated: false });
    }
  }

  const decoded = decodeToken(accessToken);
  if (!decoded) return res.status(401).json({ detail: "غير مصرح" });

  return res.json({
    authenticated: true,
    user: { id: decoded.sub, tenant_id: decoded.tenant_id, role: decoded.role },
  });
});

export default router;
