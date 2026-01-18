# app/database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Create Engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency for API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()