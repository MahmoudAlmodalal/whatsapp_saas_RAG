from fastapi import APIRouter
from pydantic import BaseModel
from app.database import get_db
from app.models.schemas import UnansweredQuestion

router = APIRouter()

class LearnRequest(BaseModel):
    question: str
    answer: str
    company_id: str = "default"
    unanswered_id: str | None = None

@router.post("/api/v1/learn")
async def learn_from_agent(req: LearnRequest):
    qa_markdown = f"## Question\n{req.question}\n\n## Answer\n{req.answer}"
    source_name = f"agent_approved_{req.question[:30].replace(' ', '_')}"

    from app.ingestion.chunker import chunk_and_store
    chunk_count = await chunk_and_store(
        markdown=qa_markdown,
        source_name=source_name,
        company_id=req.company_id,
    )

    if req.unanswered_id:
        db = next(get_db())
        try:
            q = db.query(UnansweredQuestion).filter(UnansweredQuestion.id == req.unanswered_id).first()
            if q:
                q.resolved = True
                db.commit()
        finally:
            db.close()

    return {
        "status": "learned",
        "chunks_added": chunk_count,
        "message": "تمت إضافة الإجابة إلى قاعدة المعرفة. سيستخدمها البوت في المحادثات القادمة." if chunk_count > 0 else "فشل الحفظ — تحقق من مفتاح OpenAI API.",
    }
