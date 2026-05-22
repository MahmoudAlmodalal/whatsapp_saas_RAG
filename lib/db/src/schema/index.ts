import { pgTable, text, uuid, boolean, timestamp, jsonb, integer, pgEnum } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod/v4";

// ─── Enums ────────────────────────────────────────────────────────────────────

export const subscriptionTierEnum = pgEnum("subscription_tier", ["free", "starter", "pro", "business"]);
export const documentStatusEnum   = pgEnum("document_status",   ["queued", "processing", "ready", "error"]);
export const conversationStatusEnum = pgEnum("conversation_status", ["active", "handoff", "closed"]);
export const channelEnum           = pgEnum("channel",           ["web", "telegram"]);
export const messageRoleEnum       = pgEnum("message_role",      ["customer", "ai", "agent"]);
export const userRoleEnum          = pgEnum("user_role",         ["admin", "agent"]);

// ─── Super Admins ─────────────────────────────────────────────────────────────

export const superAdminsTable = pgTable("super_admins", {
  id:           uuid("id").primaryKey().defaultRandom(),
  email:        text("email").notNull().unique(),
  passwordHash: text("password_hash").notNull(),
  name:         text("name").notNull().default("Super Admin"),
  createdAt:    timestamp("created_at").defaultNow().notNull(),
  updatedAt:    timestamp("updated_at").defaultNow().notNull(),
});

// ─── Tenants (companies) ──────────────────────────────────────────────────────

export const tenantsTable = pgTable("tenants", {
  id:                    uuid("id").primaryKey().defaultRandom(),
  name:                  text("name").notNull(),
  email:                 text("email").unique(),
  subscriptionTier:      text("subscription_tier").notNull().default("free"),
  messagesUsedThisMonth: integer("messages_used_this_month").notNull().default(0),
  isActive:              boolean("is_active").notNull().default(true),
  config:                jsonb("config").default({}),
  createdAt:             timestamp("created_at").defaultNow().notNull(),
  updatedAt:             timestamp("updated_at").defaultNow().notNull(),
});

// ─── Tenant Users ─────────────────────────────────────────────────────────────

export const tenantUsersTable = pgTable("tenant_users", {
  id:           uuid("id").primaryKey().defaultRandom(),
  tenantId:     uuid("tenant_id").notNull().references(() => tenantsTable.id, { onDelete: "cascade" }),
  email:        text("email").notNull().unique(),
  passwordHash: text("password_hash"),
  name:         text("name").notNull().default(""),
  role:         text("role").notNull().default("admin"),
  isActive:     boolean("is_active").notNull().default(true),
  createdAt:    timestamp("created_at").defaultNow().notNull(),
  updatedAt:    timestamp("updated_at").defaultNow().notNull(),
});

// ─── Documents (knowledge base) ───────────────────────────────────────────────

export const documentsTable = pgTable("documents", {
  id:           uuid("id").primaryKey().defaultRandom(),
  tenantId:     uuid("tenant_id").notNull().references(() => tenantsTable.id, { onDelete: "cascade" }),
  fileName:     text("file_name").notNull(),
  originalName: text("original_name").notNull(),
  fileType:     text("file_type").notNull(),
  fileSize:     integer("file_size").notNull().default(0),
  status:       text("status").notNull().default("queued"),
  chunkCount:   integer("chunk_count"),
  errorMessage: text("error_message"),
  uploadedAt:   timestamp("uploaded_at").defaultNow().notNull(),
  processedAt:  timestamp("processed_at"),
});

// ─── Conversations ────────────────────────────────────────────────────────────

export const conversationsTable = pgTable("conversations", {
  id:                 uuid("id").primaryKey().defaultRandom(),
  tenantId:           uuid("tenant_id").notNull().references(() => tenantsTable.id, { onDelete: "cascade" }),
  channel:            text("channel").notNull().default("web"),
  customerIdentifier: text("customer_identifier").notNull(),
  status:             text("status").notNull().default("active"),
  aiMode:             boolean("ai_mode").notNull().default(true),
  messageCount:       integer("message_count").notNull().default(0),
  metadata:           jsonb("metadata").default({}),
  startedAt:          timestamp("started_at").defaultNow().notNull(),
  lastMessageAt:      timestamp("last_message_at").defaultNow().notNull(),
});

// ─── Messages ─────────────────────────────────────────────────────────────────

export const messagesTable = pgTable("messages", {
  id:             uuid("id").primaryKey().defaultRandom(),
  conversationId: uuid("conversation_id").notNull().references(() => conversationsTable.id, { onDelete: "cascade" }),
  role:           text("role").notNull(),
  content:        text("content").notNull(),
  metadata:       jsonb("metadata").default({}),
  createdAt:      timestamp("created_at").defaultNow().notNull(),
});

// ─── System Config ────────────────────────────────────────────────────────────

export const systemConfigTable = pgTable("system_config", {
  key:       text("key").primaryKey(),
  value:     text("value").notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

// ─── Zod Schemas ─────────────────────────────────────────────────────────────

export const insertSuperAdminSchema   = createInsertSchema(superAdminsTable).omit({ id: true, createdAt: true, updatedAt: true });
export const insertTenantSchema       = createInsertSchema(tenantsTable).omit({ id: true, createdAt: true, updatedAt: true, messagesUsedThisMonth: true });
export const insertTenantUserSchema   = createInsertSchema(tenantUsersTable).omit({ id: true, createdAt: true, updatedAt: true });
export const insertDocumentSchema     = createInsertSchema(documentsTable).omit({ id: true, uploadedAt: true, processedAt: true });
export const insertConversationSchema = createInsertSchema(conversationsTable).omit({ id: true, startedAt: true, lastMessageAt: true });
export const insertMessageSchema      = createInsertSchema(messagesTable).omit({ id: true, createdAt: true });

// ─── TypeScript Types ─────────────────────────────────────────────────────────

export type SuperAdmin    = typeof superAdminsTable.$inferSelect;
export type Tenant        = typeof tenantsTable.$inferSelect;
export type TenantUser    = typeof tenantUsersTable.$inferSelect;
export type Document      = typeof documentsTable.$inferSelect;
export type Conversation  = typeof conversationsTable.$inferSelect;
export type Message       = typeof messagesTable.$inferSelect;
export type SystemConfig  = typeof systemConfigTable.$inferSelect;

export type InsertSuperAdmin    = z.infer<typeof insertSuperAdminSchema>;
export type InsertTenant        = z.infer<typeof insertTenantSchema>;
export type InsertTenantUser    = z.infer<typeof insertTenantUserSchema>;
export type InsertDocument      = z.infer<typeof insertDocumentSchema>;
export type InsertConversation  = z.infer<typeof insertConversationSchema>;
export type InsertMessage       = z.infer<typeof insertMessageSchema>;
