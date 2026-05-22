from fastapi import APIRouter
from sqlalchemy import func, desc
from app.database import get_db
from app.models.schemas import Message, UnansweredQuestion, Handoff, Conversation, KnowledgeDocument

router = APIRouter()

@router.get("/api/v1/analytics")
async def get_analytics(company_id: str = "default"):
    db = next(get_db())
    try:
        total_questions = (
            db.query(Message)
            .filter(Message.role == "user")
            .count()
        )

        answered = (
            db.query(Message)
            .filter(Message.role == "assistant", Message.strategy_used == "rag")
            .count()
        )

        unanswered_list = (
            db.query(UnansweredQuestion)
            .filter(UnansweredQuestion.company_id == company_id, UnansweredQuestion.resolved == False)
            .order_by(desc(UnansweredQuestion.created_at))
            .limit(50)
            .all()
        )

        repeated = (
            db.query(Message.content, func.count(Message.content).label("count"))
            .filter(Message.role == "user")
            .group_by(Message.content)
            .order_by(desc("count"))
            .limit(10)
            .all()
        )

        handoff_count = db.query(Handoff).filter(Handoff.company_id == company_id).count()
        open_handoffs = db.query(Handoff).filter(Handoff.company_id == company_id, Handoff.status == "open").count()
        doc_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.company_id == company_id, KnowledgeDocument.status == "ready").count()
        conv_count = db.query(Conversation).filter(Conversation.company_id == company_id).count()

        answer_rate = round((answered / total_questions * 100) if total_questions > 0 else 0.0, 1)

        return {
            "total_questions": total_questions,
            "answered_count": answered,
            "answer_rate": answer_rate,
            "unanswered_count": len(unanswered_list),
            "handoff_count": handoff_count,
            "open_handoffs": open_handoffs,
            "document_count": doc_count,
            "conversation_count": conv_count,
            "unanswered_questions": [
                {"id": q.id, "question": q.question, "session_id": q.session_id, "created_at": q.created_at.isoformat()}
                for q in unanswered_list
            ],
            "top_repeated_questions": [
                {"question": r.content, "count": r.count}
                for r in repeated
            ],
        }
    finally:
        db.close()
