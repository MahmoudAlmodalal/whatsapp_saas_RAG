-- =============================================================================
-- rls_policies.sql
-- ─────────────────
-- Row-Level Security policies for the multi-tenant WhatsApp AI SaaS.
--
-- HOW IT WORKS:
--   1. The FastAPI app calls `SET LOCAL app.current_tenant = '<uuid>'` at the
--      start of every database transaction (see app/database.py → set_tenant_context).
--   2. These policies compare every row's tenant_id against that session variable.
--   3. Any query that does NOT set the variable will return 0 rows (or fail on
--      INSERT/UPDATE/DELETE) — safe-by-default behaviour.
--
-- HOW TO APPLY:
--   psql $DATABASE_URL -f rls_policies.sql
--   -- or via docker compose:
--   docker compose exec postgres psql -U whatsapp_user -d whatsapp_saas -f /rls_policies.sql
--
-- NOTE: This script is IDEMPOTENT — it uses CREATE POLICY IF NOT EXISTS equivalents
--       (DROP IF EXISTS → CREATE) so it can be re-run safely after a DB restore.
--
-- Tables protected:  conversations | messages | documents | document_chunks
-- Table NOT protected: tenants (superuser / service-role access only)
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- Helper: ensure RLS is still enabled (migration may have done this, but
-- running this script standalone should also be idempotent).
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE conversations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations    FORCE ROW LEVEL SECURITY;
ALTER TABLE messages         ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages         FORCE ROW LEVEL SECURITY;
ALTER TABLE documents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents        FORCE ROW LEVEL SECURITY;
ALTER TABLE document_chunks  ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks  FORCE ROW LEVEL SECURITY;


-- =============================================================================
-- conversations
-- =============================================================================
DROP POLICY IF EXISTS tenant_isolation ON conversations;

CREATE POLICY tenant_isolation ON conversations
    AS PERMISSIVE
    FOR ALL                          -- SELECT, INSERT, UPDATE, DELETE
    TO PUBLIC
    USING (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    )
    WITH CHECK (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    );


-- =============================================================================
-- messages
-- =============================================================================
DROP POLICY IF EXISTS tenant_isolation ON messages;

CREATE POLICY tenant_isolation ON messages
    AS PERMISSIVE
    FOR ALL
    TO PUBLIC
    USING (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    )
    WITH CHECK (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    );


-- =============================================================================
-- documents
-- =============================================================================
DROP POLICY IF EXISTS tenant_isolation ON documents;

CREATE POLICY tenant_isolation ON documents
    AS PERMISSIVE
    FOR ALL
    TO PUBLIC
    USING (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    )
    WITH CHECK (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    );


-- =============================================================================
-- document_chunks
-- =============================================================================
DROP POLICY IF EXISTS tenant_isolation ON document_chunks;

CREATE POLICY tenant_isolation ON document_chunks
    AS PERMISSIVE
    FOR ALL
    TO PUBLIC
    USING (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    )
    WITH CHECK (
        tenant_id = current_setting('app.current_tenant', TRUE)::uuid
    );


-- =============================================================================
-- Verification queries (optional — run manually to confirm policies are active)
-- =============================================================================
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
-- FROM   pg_policies
-- WHERE  tablename IN ('conversations','messages','documents','document_chunks')
-- ORDER  BY tablename, policyname;
