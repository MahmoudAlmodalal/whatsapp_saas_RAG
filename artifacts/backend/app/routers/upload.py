import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.schemas import KnowledgeDocument
from app.database import get_db

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx"}

@router.post("/api/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    company_id: str = Form(default="default"),
):
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"نوع الملف غير مدعوم. الأنواع المدعومة: PDF, DOCX, TXT, XLSX")

    db = next(get_db())
    try:
        doc = KnowledgeDocument(
            company_id=company_id,
            filename=filename,
            file_type=ext.lstrip("."),
            status="processing",
        )
        db.add(doc)
        db.commit()
        doc_id = doc.id
    finally:
        db.close()

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        markdown = _parse_file(tmp_path, ext)
        from app.ingestion.chunker import chunk_and_store
        chunk_count = await chunk_and_store(markdown, filename, company_id)

        db = next(get_db())
        try:
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
            if doc:
                doc.chunk_count = chunk_count
                doc.status = "ready" if chunk_count > 0 else "error"
                db.commit()
        finally:
            db.close()

        return {
            "id": doc_id,
            "filename": filename,
            "chunk_count": chunk_count,
            "status": "ready" if chunk_count > 0 else "error",
            "message": f"تمت معالجة {chunk_count} قطعة من الملف '{filename}' بنجاح." if chunk_count > 0 else "فشلت المعالجة — تحقق من مفتاح OpenAI API.",
        }
    except Exception as e:
        db = next(get_db())
        try:
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
            if doc:
                doc.status = "error"
                db.commit()
        finally:
            db.close()
        raise HTTPException(status_code=500, detail=f"خطأ في معالجة الملف: {str(e)}")
    finally:
        os.unlink(tmp_path)

@router.get("/api/v1/documents")
async def list_documents(company_id: str = "default"):
    db = next(get_db())
    try:
        docs = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.company_id == company_id)
            .order_by(KnowledgeDocument.created_at.desc())
            .all()
        )
        return {
            "documents": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "file_type": d.file_type,
                    "chunk_count": d.chunk_count,
                    "status": d.status,
                    "created_at": d.created_at.isoformat(),
                }
                for d in docs
            ]
        }
    finally:
        db.close()

@router.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    db = next(get_db())
    try:
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="الملف غير موجود")
        filename = doc.filename
        company_id = doc.company_id
        db.delete(doc)
        db.commit()
    finally:
        db.close()

    try:
        from app.config import get_settings
        import chromadb
        settings = get_settings()
        chroma = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        col = chroma.get_collection(f"company_{company_id}")
        col.delete(where={"source": filename})
    except Exception:
        pass

    return {"success": True, "message": "تم حذف الملف"}

def _parse_file(path: str, ext: str) -> str:
    if ext == ".pdf":
        from app.ingestion.pdf_parser import pdf_to_markdown
        return pdf_to_markdown(path)
    elif ext == ".docx":
        from app.ingestion.docx_parser import docx_to_markdown
        return docx_to_markdown(path)
    elif ext == ".txt":
        from app.ingestion.txt_parser import txt_to_markdown
        return txt_to_markdown(path)
    elif ext == ".xlsx":
        from app.ingestion.xlsx_parser import xlsx_to_markdown
        return xlsx_to_markdown(path)
    raise ValueError(f"Unsupported extension: {ext}")
