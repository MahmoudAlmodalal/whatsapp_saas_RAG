from app.database import get_db
from app.models.schemas import Message, UnansweredQuestion, Conversation
from app.config import get_settings

settings = get_settings()

def get_session_history(session_id: str) -> list:
    db = next(get_db())
    try:
        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(settings.MAX_CONTEXT_MESSAGES)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]
    finally:
        db.close()

def save_message(session_id: str, role: str, content: str, language: str,
                 confidence: float = None, strategy_used: str = None):
    db = next(get_db())
    try:
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
            language=language,
            confidence=confidence,
            strategy_used=strategy_used,
        )
        db.add(msg)
        db.commit()
    finally:
        db.close()

def log_unanswered(question: str, session_id: str, company_id: str = "default"):
    db = next(get_db())
    try:
        entry = UnansweredQuestion(
            question=question,
            session_id=session_id,
            company_id=company_id,
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()

def ensure_conversation(session_id: str, company_id: str = "default",
                        channel: str = "web", language: str = "ar"):
    db = next(get_db())
    try:
        existing = db.query(Conversation).filter(Conversation.session_id == session_id).first()
        if not existing:
            conv = Conversation(
                session_id=session_id,
                company_id=company_id,
                channel=channel,
                language=language,
            )
            db.add(conv)
            db.commit()
    finally:
        db.close()
