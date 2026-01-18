# app/models/faq.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database.connection import Base

class FAQ(Base):
    """
    Stores Pre-populated FAQs manageable by Admins.
    Guide Section: 5.3 & 7.3
    """
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    language = Column(String, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())