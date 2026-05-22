from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from app.database import get_db
from app.models.schemas import Handoff, Message

router = APIRouter()

class HandoffCreate(BaseModel):
    session_id: str
    company_id: str = "default"
    trigger_reason: str = "user_requested"

class HandoffReply(BaseModel):
    agent_reply: str

@router.post("/api/v1/handoff")
async def create_handoff(req: HandoffCreate):
    db = next(get_db())
    try:
        existing = (
            db.query(Handoff)
            .filter(Handoff.session_id == req.session_id, Handoff.status == "open")
            .first()
        )
        if existing:
            return {"handoff_id": existing.id, "status": existing.status, "already_exists": True}
        handoff = Handoff(
            session_id=req.session_id,
            company_id=req.company_id,
            trigger_reason=req.trigger_reason,
            status="open",
        )
        db.add(handoff)
        db.commit()
        return {"handoff_id": handoff.id, "status": "open"}
    finally:
        db.close()

@router.get("/api/v1/handoffs")
async def list_handoffs(status: str = "open", company_id: str = "default"):
    db = next(get_db())
    try:
        q = db.query(Handoff).filter(Handoff.company_id == company_id)
        if status != "all":
            q = q.filter(Handoff.status == status)
        handoffs = q.order_by(desc(Handoff.created_at)).all()
        result = []
        for h in handoffs:
            history = (
                db.query(Message)
                .filter(Message.session_id == h.session_id)
                .order_by(Message.created_at)
                .limit(20)
                .all()
            )
            result.append({
                "id": h.id,
                "session_id": h.session_id,
                "trigger_reason": h.trigger_reason,
                "status": h.status,
                "agent_reply": h.agent_reply,
                "created_at": h.created_at.isoformat(),
                "history": [{"role": m.role, "content": m.content} for m in history],
            })
        return {"handoffs": result}
    finally:
        db.close()

@router.patch("/api/v1/handoffs/{handoff_id}")
async def update_handoff(handoff_id: str, req: HandoffReply):
    db = next(get_db())
    try:
        handoff = db.query(Handoff).filter(Handoff.id == handoff_id).first()
        if not handoff:
            raise HTTPException(status_code=404, detail="Handoff not found")
        handoff.agent_reply = req.agent_reply
        handoff.status = "closed"
        db.commit()
        return {"success": True, "status": "closed"}
    finally:
        db.close()

@router.patch("/api/v1/handoffs/{handoff_id}/close")
async def close_handoff(handoff_id: str):
    db = next(get_db())
    try:
        handoff = db.query(Handoff).filter(Handoff.id == handoff_id).first()
        if not handoff:
            raise HTTPException(status_code=404, detail="Handoff not found")
        handoff.status = "closed"
        db.commit()
        return {"success": True}
    finally:
        db.close()
