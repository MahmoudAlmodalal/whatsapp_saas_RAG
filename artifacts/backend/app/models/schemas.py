import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean
from app.database import Base

def _uuid():
    return str(uuid.uuid4())

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, index=True)
    company_id = Column(String, index=True, default="default")
    channel = Column(String, default="web")
    language = Column(String, default="ar")
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    language = Column(String, default="ar")
    confidence = Column(Float, nullable=True)
    strategy_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UnansweredQuestion(Base):
    __tablename__ = "unanswered_questions"
    id = Column(String, primary_key=True, default=_uuid)
    question = Column(Text)
    session_id = Column(String)
    company_id = Column(String, default="default")
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Handoff(Base):
    __tablename__ = "handoffs"
    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String)
    company_id = Column(String, default="default")
    trigger_reason = Column(String)
    status = Column(String, default="open")
    agent_reply = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id = Column(String, primary_key=True, default=_uuid)
    company_id = Column(String, default="default")
    filename = Column(String)
    file_type = Column(String)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)

class CompanySettings(Base):
    __tablename__ = "company_settings"
    id = Column(String, primary_key=True, default="default")
    company_name = Column(String, default="شركتي")
    persona_name = Column(String, default="نصيح")
    tone = Column(String, default="professional")
    language_preference = Column(String, default="auto")
    system_prompt_extra = Column(Text, nullable=True)
    telegram_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
