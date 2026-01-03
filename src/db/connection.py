import logging

from src.config import DB_URL

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

logger = logging.getLogger(__name__)

try:
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Error creating db_engine: {e}")
    exit()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session | None:
    try:
        db = SessionLocal()
        return db
    except Exception as e:
        logger.info(f"Error creating db_session: {e}")
        return None