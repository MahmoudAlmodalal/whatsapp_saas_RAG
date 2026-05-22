import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
os.makedirs(_DATA_DIR, exist_ok=True)
SQLITE_URL = f"sqlite:///{os.path.join(_DATA_DIR, 'naseh.db')}"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def create_tables():
    from app.models import schemas  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
