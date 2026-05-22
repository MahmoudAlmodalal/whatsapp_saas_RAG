"""create_missing_tables

Revision ID: 0007
Revises: 0006_add_super_admin_role
Create Date: 2026-05-22

Idempotent migration: creates any missing core tables (users, conversations,
messages, documents, document_chunks) using DO $$ IF NOT EXISTS $$ guards.
Safe to run on a DB that was bootstrapped via Drizzle push.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006_add_super_admin_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


def upgrade() -> None:
    conn = op.get_bind()

    # ── 0. Ensure ENUM types exist ────────────────────────────────────────────
    _exec("DO $$ BEGIN CREATE TYPE subscription_tier_enum AS ENUM ('free','starter','pro','business','basic','enterprise'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    _exec("DO $$ BEGIN CREATE TYPE conversation_status_enum AS ENUM ('active','handoff','closed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    _exec("DO $$ BEGIN CREATE TYPE message_role_enum AS ENUM ('customer','ai','agent'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    _exec("DO $$ BEGIN CREATE TYPE document_status_enum AS ENUM ('queued','processing','ready','failed','error'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # ── 1. Extend tenants table (add missing columns safely) ──────────────────
    # messages_used_this_month
    _exec("""
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='tenants' AND column_name='messages_used_this_month'
          ) THEN
            ALTER TABLE tenants ADD COLUMN messages_used_this_month INTEGER NOT NULL DEFAULT 0;
          END IF;
        END $$;
    """)
    # email on tenants
    _exec("""
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='tenants' AND column_name='email'
          ) THEN
            ALTER TABLE tenants ADD COLUMN email VARCHAR(255);
          END IF;
        END $$;
    """)
    # Update subscription_tier default to 'free'
    _exec("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='tenants' AND column_name='subscription_tier'
          ) THEN
            ALTER TABLE tenants ALTER COLUMN subscription_tier SET DEFAULT 'free';
          END IF;
        END $$;
    """)
    # Add new subscription tier values if enum exists
    _exec("DO $$ BEGIN ALTER TYPE subscription_tier_enum ADD VALUE IF NOT EXISTS 'free'; EXCEPTION WHEN others THEN NULL; END $$;")
    _exec("DO $$ BEGIN ALTER TYPE subscription_tier_enum ADD VALUE IF NOT EXISTS 'starter'; EXCEPTION WHEN others THEN NULL; END $$;")
    _exec("DO $$ BEGIN ALTER TYPE subscription_tier_enum ADD VALUE IF NOT EXISTS 'pro'; EXCEPTION WHEN others THEN NULL; END $$;")
    _exec("DO $$ BEGIN ALTER TYPE subscription_tier_enum ADD VALUE IF NOT EXISTS 'business'; EXCEPTION WHEN others THEN NULL; END $$;")

    # ── 2. users table ────────────────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'agent',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    _exec("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);")
    _exec("CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id);")
    _exec("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")

    # ── 3. conversations table ────────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            channel VARCHAR(20) NOT NULL DEFAULT 'web',
            customer_phone VARCHAR(100),
            customer_identifier VARCHAR(255) NOT NULL DEFAULT '',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            ai_mode BOOLEAN NOT NULL DEFAULT true,
            message_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_message_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{}'
        );
    """)
    _exec("CREATE INDEX IF NOT EXISTS ix_conversations_tenant_id ON conversations(tenant_id);")
    _exec("CREATE INDEX IF NOT EXISTS ix_conversations_status ON conversations(status);")
    _exec("CREATE INDEX IF NOT EXISTS ix_conversations_channel ON conversations(channel);")
    _exec("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;")
    _exec("DROP POLICY IF EXISTS tenant_isolation ON conversations;")
    _exec("""
        CREATE POLICY tenant_isolation ON conversations
            AS PERMISSIVE FOR ALL TO PUBLIC
            USING (tenant_id = current_setting('app.current_tenant', TRUE)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE)::uuid);
    """)

    # ── 4. messages table ─────────────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            wa_message_id VARCHAR(255) UNIQUE,
            tokens_used INTEGER,
            model_used VARCHAR(100),
            latency_ms INTEGER,
            confidence FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{}'
        );
    """)
    _exec("CREATE INDEX IF NOT EXISTS ix_messages_tenant_id ON messages(tenant_id);")
    _exec("CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id);")
    _exec("CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at);")
    _exec("ALTER TABLE messages ENABLE ROW LEVEL SECURITY;")
    _exec("DROP POLICY IF EXISTS tenant_isolation ON messages;")
    _exec("""
        CREATE POLICY tenant_isolation ON messages
            AS PERMISSIVE FOR ALL TO PUBLIC
            USING (tenant_id = current_setting('app.current_tenant', TRUE)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE)::uuid);
    """)

    # ── 5. documents table ────────────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            file_name VARCHAR(500) NOT NULL,
            original_name VARCHAR(500),
            file_type VARCHAR(50) NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            storage_path TEXT,
            chunk_count INTEGER,
            error_message TEXT,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'
        );
    """)
    _exec("CREATE INDEX IF NOT EXISTS ix_documents_tenant_id ON documents(tenant_id);")
    _exec("CREATE INDEX IF NOT EXISTS ix_documents_status ON documents(status);")
    _exec("ALTER TABLE documents ENABLE ROW LEVEL SECURITY;")
    _exec("DROP POLICY IF EXISTS tenant_isolation ON documents;")
    _exec("""
        CREATE POLICY tenant_isolation ON documents
            AS PERMISSIVE FOR ALL TO PUBLIC
            USING (tenant_id = current_setting('app.current_tenant', TRUE)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE)::uuid);
    """)

    # ── 6. document_chunks table ──────────────────────────────────────────────
    # Only create if pgvector extension is available
    _exec("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                EXECUTE '
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                        document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        content TEXT NOT NULL,
                        embedding vector(1536),
                        chunk_index INTEGER NOT NULL DEFAULT 0,
                        metadata JSONB NOT NULL DEFAULT ''{}'',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                ';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_document_chunks_tenant_id ON document_chunks(tenant_id)';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id ON document_chunks(document_id)';
                BEGIN
                    EXECUTE ''
                        'CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw '
                        'ON document_chunks USING hnsw (embedding vector_cosine_ops) '
                        'WITH (m = 16, ef_construction = 64)'
                    '';
                EXCEPTION WHEN others THEN NULL;
                END;
            END IF;
        END $$;
    """)

    # ── 7. Ensure super_admin role exists in user_role_enum if present ────────
    _exec("DO $$ BEGIN ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'super_admin'; EXCEPTION WHEN others THEN NULL; END $$;")


def downgrade() -> None:
    # Safe no-op: individual table drops are risky due to FK constraints.
    # Run manually if needed: DROP TABLE IF EXISTS document_chunks, documents, messages, conversations, users CASCADE;
    pass
