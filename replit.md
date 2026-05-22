# رسن (Rasan)

A SaaS chatbot platform — Arabic RTL dashboard for companies to upload their data (PDF/DOCX) and instantly get an AI chatbot for their website or Telegram, without any technical expertise.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 8080)
- `pnpm --filter @workspace/whatsapp-dashboard run dev` — run the frontend (port 23097)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string
- Optional env: `BACKEND_API_URL` — Python FastAPI backend URL (default: `http://localhost:8001/api/v1`)

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: React 18 + Vite, wouter (routing), @tanstack/react-query, Tailwind CSS v4, lucide-react
- API: Express 5 (proxy layer for Python FastAPI backend)
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `artifacts/whatsapp-dashboard/` — React + Vite frontend (preview at `/`)
- `artifacts/api-server/` — Express API server (preview at `/api`, port 8080)
  - `src/routes/auth.ts` — login/logout/me (sets httpOnly JWT cookies, proxies to Python backend)
  - `src/routes/v1proxy.ts` — transparent proxy for all `/api/v1/*` calls to Python backend
  - `src/lib/auth.ts` — JWT decode/expiry/refresh helpers
- `lib/api-spec/` — OpenAPI spec (source of truth for API contract)
- `lib/api-client-react/` — Generated React Query hooks from spec
- `lib/db/` — Drizzle ORM schema + migrations

## Architecture decisions

- **Auth via httpOnly cookies**: The Express layer acts as a BFF (Backend for Frontend) — it proxies login to Python, stores JWT in httpOnly cookies (not localStorage), and attaches Bearer tokens to backend proxied calls.
- **`/api/v1/*` transparent proxy**: All dashboard API calls go to `/api/v1/*` → Express → Python FastAPI at `BACKEND_API_URL/v1/*`. Tokens are injected server-side from cookies.
- **Tailwind v4**: Uses `@import "tailwindcss"` (not old `@tailwind base/components/utilities` directives) with `@tailwindcss/vite` plugin.
- **RTL + Tajawal font**: HTML lang=ar dir=rtl set in index.html; Tajawal Google Font loaded in HTML head.
- **wouter routing**: App uses wouter with `base={import.meta.env.BASE_URL}` so all routes work under the Replit preview path prefix.

## Product — رسن SaaS Platform

### Users
- **Admin (Super Admin)**: manages all companies, subscriptions, accounts
- **Company**: uploads knowledge base files, configures chatbot, deploys to website/Telegram, views stats
- **End Customer**: chats with the AI bot on the company's site or via Telegram

### Pricing Plans
| Plan | Price | Conversations/month |
|------|-------|---------------------|
| مجاني (Free) | $0 | 50 |
| Starter | $9/mo | 500 |
| Pro | $19/mo | 2,000 |
| Business | $39/mo | Unlimited |

### Dashboard Pages (Company)
- **الرئيسية (Overview)** — stats: messages used vs plan limit, docs count, bot status, setup checklist
- **قاعدة المعرفة (Documents)** — upload/delete PDF, DOCX, TXT, XLSX files for RAG
- **المحادثات (Conversations)** — list/filter chats by status, open detail view
- **التكامل والنشر (Integration)** — website embed code snippet + Telegram bot token setup
- **إعدادات الشات بوت (Settings)** — AI persona name, language, tone, confidence threshold, handoff keywords

### Super Admin Pages
- **الشركات (Tenants)** — manage all companies + subscription tiers
- **الحسابات (Accounts)** — manage admin users
- **إعدادات النظام (System Settings)** — platform-wide config

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- Express 5 uses `/*path` wildcard syntax (not `/*`) — path-to-regexp v8 breaking change.
- The api-server runs at port 8080 in Replit's routing; the frontend Vite dev server runs at port 23097.
- Auth routes are at `/api/auth/*` (not `/auth/*`) so they're correctly routed through the api-server path.
- Always restart the api-server workflow after code changes (it runs build + start).

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
- Original project was a Next.js v0/Vercel import — migrated to Vite + React + Express
