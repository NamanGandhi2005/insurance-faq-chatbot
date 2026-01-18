# app/models/product.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    pdfs = relationship("PDFDocument", back_populates="product")
    audits = relationship("AuditLog", back_populates="product")

class PDFDocument(Base):
    __tablename__ = "pdf_documents"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    file_name = Column(String)
    file_path = Column(String)
    file_size = Column(Integer) # in bytes
    language = Column(String, default="en")
    status = Column(String, default="uploaded") # uploaded, processing, completed, error
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("Product", back_populates="pdfs")