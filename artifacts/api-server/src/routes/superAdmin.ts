import { Router } from "express";
import type { Request, Response, NextFunction } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { db, superAdminsTable, tenantsTable, tenantUsersTable, systemConfigTable } from "@workspace/db";
import { eq } from "drizzle-orm";

const router = Router();

const SUPER_ADMIN_JWT_SECRET = process.env.SUPER_ADMIN_JWT_SECRET || "super-admin-dev-secret-change-in-prod";
const COOKIE_MAX_AGE = 8 * 3600 * 1000;

function signSuperAdminToken(adminId: string, email: string) {
  return jwt.sign(
    { sub: adminId, email, role: "super_admin", tenant_id: null },
    SUPER_ADMIN_JWT_SECRET,
    { expiresIn: "8h" }
  );
}

function requireSuperAdmin(req: Request, res: Response, next: NextFunction) {
  const token = req.cookies?.super_admin_token;
  if (!token) return res.status(401).json({ detail: "غير مصرح" });
  try {
    const decoded = jwt.verify(token, SUPER_ADMIN_JWT_SECRET) as { sub: string; email: string; role: string };
    if (decoded.role !== "super_admin") return res.status(403).json({ detail: "ممنوع" });
    (req as any).superAdmin = decoded;
    next();
  } catch {
    return res.status(401).json({ detail: "جلسة منتهية الصلاحية" });
  }
}

router.post("/super-admin/logout", (req: Request, res: Response) => {
  res.clearCookie("super_admin_token", { path: "/" });
  return res.json({ success: true });
});

router.get("/super-admin/me", requireSuperAdmin, async (req: Request, res: Response) => {
  const admin = (req as any).superAdmin;
  return res.json({ authenticated: true, admin: { id: admin.sub, email: admin.email, role: "super_admin" } });
});

router.get("/super-admin/tenants", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const tenants = await db.select().from(tenantsTable).orderBy(tenantsTable.createdAt);
    return res.json(tenants);
  } catch (err) {
    req.log.error({ err }, "List tenants error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.post("/super-admin/tenants", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { name, whatsappNumber, subscriptionTier } = req.body;
    if (!name) return res.status(400).json({ detail: "اسم الشريك مطلوب" });
    const [tenant] = await db.insert(tenantsTable).values({
      name,
      whatsappNumber: whatsappNumber || null,
      subscriptionTier: subscriptionTier || "basic",
      isActive: true,
    }).returning();
    return res.json(tenant);
  } catch (err) {
    req.log.error({ err }, "Create tenant error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.patch("/super-admin/tenants/:id", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { name, whatsappNumber, subscriptionTier, isActive } = req.body;
    const [updated] = await db.update(tenantsTable)
      .set({
        ...(name !== undefined && { name }),
        ...(whatsappNumber !== undefined && { whatsappNumber }),
        ...(subscriptionTier !== undefined && { subscriptionTier }),
        ...(isActive !== undefined && { isActive }),
        updatedAt: new Date(),
      })
      .where(eq(tenantsTable.id, id))
      .returning();
    if (!updated) return res.status(404).json({ detail: "الشريك غير موجود" });
    return res.json(updated);
  } catch (err) {
    req.log.error({ err }, "Update tenant error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.delete("/super-admin/tenants/:id", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    await db.delete(tenantsTable).where(eq(tenantsTable.id, id));
    return res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "Delete tenant error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.get("/super-admin/tenants/:id/users", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const users = await db.select().from(tenantUsersTable).where(eq(tenantUsersTable.tenantId, id));
    return res.json(users);
  } catch (err) {
    req.log.error({ err }, "List tenant users error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.post("/super-admin/tenants/:id/users", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { email, name, role, password } = req.body;
    if (!email) return res.status(400).json({ detail: "البريد الإلكتروني مطلوب" });
    if (!password) return res.status(400).json({ detail: "كلمة المرور مطلوبة" });
    const passwordHash = await bcrypt.hash(password, 10);
    const [user] = await db.insert(tenantUsersTable).values({
      tenantId: id,
      email: email.toLowerCase(),
      passwordHash,
      name: name || "",
      role: role || "agent",
      isActive: true,
    }).returning();
    const { passwordHash: _ph, ...safeUser } = user;
    return res.json(safeUser);
  } catch (err) {
    req.log.error({ err }, "Create tenant user error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.patch("/super-admin/users/:id", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { name, role, isActive, password } = req.body;
    const updateData: Record<string, unknown> = { updatedAt: new Date() };
    if (name !== undefined) updateData.name = name;
    if (role !== undefined) updateData.role = role;
    if (isActive !== undefined) updateData.isActive = isActive;
    if (password) updateData.passwordHash = await bcrypt.hash(password, 10);
    const [updated] = await db.update(tenantUsersTable)
      .set(updateData)
      .where(eq(tenantUsersTable.id, id))
      .returning();
    if (!updated) return res.status(404).json({ detail: "المستخدم غير موجود" });
    const { passwordHash: _ph, ...safeUser } = updated;
    return res.json(safeUser);
  } catch (err) {
    req.log.error({ err }, "Update user error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.delete("/super-admin/users/:id", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    await db.delete(tenantUsersTable).where(eq(tenantUsersTable.id, id));
    return res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "Delete user error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.get("/super-admin/settings", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const rows = await db.select().from(systemConfigTable);
    const settings: Record<string, string> = {};
    for (const row of rows) {
      if (row.key === "deepseek_api_key") {
        settings[row.key] = row.value ? "••••••••" + row.value.slice(-4) : "";
      } else {
        settings[row.key] = row.value;
      }
    }
    return res.json(settings);
  } catch (err) {
    req.log.error({ err }, "Get settings error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.put("/super-admin/settings", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const { deepseek_api_key } = req.body;
    if (deepseek_api_key !== undefined) {
      if (deepseek_api_key && !deepseek_api_key.startsWith("••")) {
        await db.insert(systemConfigTable)
          .values({ key: "deepseek_api_key", value: deepseek_api_key, updatedAt: new Date() })
          .onConflictDoUpdate({ target: systemConfigTable.key, set: { value: deepseek_api_key, updatedAt: new Date() } });
      }
    }
    return res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "Update settings error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

router.post("/super-admin/seed", async (req: Request, res: Response) => {
  try {
    const { eq } = await import("drizzle-orm");
    const [existing] = await db.select().from(superAdminsTable).where(eq(superAdminsTable.email, "g@g.com")).limit(1);
    if (existing) return res.json({ message: "الحساب موجود بالفعل", id: existing.id });

    const passwordHash = await bcrypt.hash("1", 10);
    const [admin] = await db.insert(superAdminsTable).values({
      email: "g@g.com",
      passwordHash,
      name: "Super Admin",
    }).returning();
    return res.json({ message: "تم إنشاء الحساب بنجاح", id: admin.id });
  } catch (err) {
    req.log.error({ err }, "Seed error");
    return res.status(500).json({ detail: "خطأ في الخادم" });
  }
});

export default router;
export { requireSuperAdmin };
