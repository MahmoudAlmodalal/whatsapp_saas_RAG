import { db, tenantsTable, tenantUsersTable } from "@workspace/db";
import bcrypt from "bcryptjs";

const hash = await bcrypt.hash("demo123", 10);

const [tenant] = await db
  .insert(tenantsTable)
  .values({
    name: "نصيح Demo",
    email: "demo@naseh.ai",
    subscriptionTier: "pro",
    isActive: true,
  })
  .onConflictDoUpdate({
    target: tenantsTable.email,
    set: { name: "نصيح Demo", subscriptionTier: "pro", isActive: true },
  })
  .returning();

await db
  .insert(tenantUsersTable)
  .values({
    tenantId: tenant.id,
    email: "demo@naseh.ai",
    passwordHash: hash,
    name: "Demo Company",
    role: "admin",
    isActive: true,
  })
  .onConflictDoUpdate({
    target: tenantUsersTable.email,
    set: { passwordHash: hash, isActive: true, tenantId: tenant.id },
  });

console.log("✓ Demo user seeded: demo@naseh.ai / demo123  tenant:", tenant.id);
process.exit(0);
