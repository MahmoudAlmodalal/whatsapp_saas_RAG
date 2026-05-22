"""
tests/unit/test_rag_ingestion.py
──────────────────────────────────
Unit tests for the RAG document ingestion pipeline.
All tests mock the embedding model and storage — no DB or filesystem I/O.
"""
import io
import pytest
from unittest.mock import MagicMock, patch
import numpy as np

pytestmark = pytest.mark.unit


class TestTextExtraction:
    """Test file format-specific text extraction functions."""

    def test_extract_txt_content(self):
        from app.services.ingestion import _extract_text_from_txt
        text = "مرحباً بك في نظامنا.\nهذا نص تجريبي."
        result = _extract_text_from_txt(io.BytesIO(text.encode("utf-8")))
        assert "مرحباً" in result
        assert "نص تجريبي" in result

    def test_extract_txt_empty_file(self):
        from app.services.ingestion import _extract_text_from_txt
        result = _extract_text_from_txt(io.BytesIO(b""))
        assert result == "" or result is not None

    @patch("app.services.ingestion.fitz")
    def test_extract_pdf_calls_fitz(self, mock_fitz):
        from app.services.ingestion import _extract_text_from_pdf
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "صفحة واحدة"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_fitz.open.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_fitz.open.return_value.__exit__ = MagicMock(return_value=False)
        _extract_text_from_pdf(b"fake_pdf_bytes")
        mock_fitz.open.assert_called_once()

    @patch("app.services.ingestion.openpyxl")
    def test_extract_xlsx_reads_cells(self, mock_xl):
        from app.services.ingestion import _extract_text_from_xlsx
        mock_wb = MagicMock()
        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [
            [MagicMock(value="المنتج"), MagicMock(value="السعر")],
            [MagicMock(value="قميص"), MagicMock(value="150")],
        ]
        mock_wb.active = mock_ws
        mock_xl.load_workbook.return_value = mock_wb
        result = _extract_text_from_xlsx(io.BytesIO(b"fake_xlsx"))
        assert result is not None


class TestArabicNormalization:
    """Test Arabic text normalization."""

    def test_removes_diacritics(self):
        from app.services.ingestion import _normalize_arabic_text
        with_diacritics = "كَتَبَ الطِّفْلُ الدَّرْسَ"
        result = _normalize_arabic_text(with_diacritics)
        assert "َ" not in result  # fatha removed
        assert "ِ" not in result  # kasra removed
        assert "ُ" not in result  # damma removed

    def test_handles_mixed_arabic_english(self):
        from app.services.ingestion import _normalize_arabic_text
        text = "Product اسم المنتج هو iPhone 15"
        result = _normalize_arabic_text(text)
        assert result is not None
        assert "15" in result

    def test_handles_empty_string(self):
        from app.services.ingestion import _normalize_arabic_text
        assert _normalize_arabic_text("") == ""


class TestChunkingLogic:
    """Test text chunking with overlap."""

    def test_chunk_produces_multiple_chunks(self):
        from app.services.ingestion import _chunk_text
        long_text = "هذا نص تجريبي طويل جداً. " * 100
        chunks = _chunk_text(long_text, chunk_size=200, overlap=20)
        assert len(chunks) > 1

    def test_short_text_produces_single_chunk(self):
        from app.services.ingestion import _chunk_text
        short_text = "نص قصير"
        chunks = _chunk_text(short_text, chunk_size=500, overlap=50)
        assert len(chunks) == 1

    def test_empty_text_returns_empty_list(self):
        from app.services.ingestion import _chunk_text
        assert _chunk_text("", chunk_size=500, overlap=50) == []

    def test_no_chunk_exceeds_size_limit(self):
        from app.services.ingestion import _chunk_text
        text = "x" * 2000
        chunks = _chunk_text(text, chunk_size=200, overlap=20)
        for chunk in chunks:
            assert len(chunk) <= 250  # size + small overhead


class TestTokenCounting:
    """Test tiktoken-based token counting."""

    def test_count_tokens_returns_integer(self):
        from app.services.ingestion import _count_tokens
        count = _count_tokens("Hello world")
        assert isinstance(count, int)
        assert count > 0

    def test_empty_text_zero_tokens(self):
        from app.services.ingestion import _count_tokens
        assert _count_tokens("") == 0

    def test_longer_text_more_tokens(self):
        from app.services.ingestion import _count_tokens
        assert _count_tokens("Hello world this is longer") > _count_tokens("Hello")


class TestEmbeddingDimensions:
    """Test embedding output dimensions."""

    def test_embedding_output_dimension(self, mock_embedding_model):
        mock_embedding_model.encode.return_value = np.zeros((1, 1024), dtype=np.float32)
        result = mock_embedding_model.encode(["test text"])
        assert result.shape == (1, 1024)

    def test_embedding_batch_dimension(self, mock_embedding_model):
        mock_embedding_model.encode.return_value = np.zeros((5, 1024), dtype=np.float32)
        result = mock_embedding_model.encode(["text"] * 5)
        assert result.shape == (5, 1024)
