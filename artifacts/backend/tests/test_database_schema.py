import pytest
from sqlalchemy import text


pytestmark = pytest.mark.asyncio


async def test_pgvector_extension_and_hnsw_index_exist(db_session):
    extensions = await db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname IN ('pgcrypto', 'vector')")
    )
    assert {row[0] for row in extensions.all()} == {"pgcrypto", "vector"}

    index_result = await db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'document_chunks'
              AND indexname = 'ix_document_chunks_embedding_hnsw'
            """
        )
    )
    indexdef = index_result.scalar_one()
    assert "USING hnsw" in indexdef
    assert "vector_cosine_ops" in indexdef


async def test_metadata_columns_match_public_schema(db_session):
    result = await db_session.execute(
        text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('conversations', 'document_chunks')
              AND column_name IN ('metadata', 'meta_data')
            """
        )
    )
    columns = {(row.table_name, row.column_name) for row in result.all()}

    assert ("conversations", "metadata") in columns
    assert ("document_chunks", "metadata") in columns
    assert ("conversations", "meta_data") not in columns
    assert ("document_chunks", "meta_data") not in columns


async def test_tenant_scoped_tables_have_rls_and_policy(db_session):
    table_names = {"conversations", "messages", "documents", "document_chunks"}

    rls_result = await db_session.execute(
        text(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname IN ('conversations', 'messages', 'documents', 'document_chunks')
            """
        )
    )
    rls_rows = {row.relname: row for row in rls_result.all()}

    assert set(rls_rows) == table_names
    assert all(row.relrowsecurity for row in rls_rows.values())
    assert all(row.relforcerowsecurity for row in rls_rows.values())

    policies_result = await db_session.execute(
        text(
            """
            SELECT tablename
            FROM pg_policies
            WHERE schemaname = 'public'
              AND policyname = 'tenant_isolation'
              AND tablename IN ('conversations', 'messages', 'documents', 'document_chunks')
            """
        )
    )
    assert {row.tablename for row in policies_result.all()} == table_names


async def test_users_table_is_not_rls_protected_for_login(db_session):
    rls_result = await db_session.execute(
        text(
            """
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = 'users'
            """
        )
    )
    relrowsecurity, relforcerowsecurity = rls_result.one()

    assert relrowsecurity is False
    assert relforcerowsecurity is False

    policies_result = await db_session.execute(
        text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = 'users'")
    )
    assert policies_result.scalar_one() == 0
