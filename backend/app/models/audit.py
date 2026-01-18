# app/models/audit.py
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True) # Nullable if public access allowed
    product_id = Column(Integer, ForeignKey("products.id"))
    question = Column(Text)
    answer = Column(Text)
    language = Column(String, default="en")
    response_time_ms = Column(Float)
    sources = Column(Text) # JSON string of sources
    is_cached = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="audits")