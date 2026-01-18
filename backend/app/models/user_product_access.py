# app/models/user_product_access.py
from sqlalchemy import Column, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.sql import func
from app.database.connection import Base

class UserProductAccess(Base):
    """
    Controls which users can access which product bots.
    Guide Section: 9.2
    """
    __tablename__ = "user_product_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    access_granted = Column(Boolean, default=True)
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=True) # ID of admin who granted it
    granted_at = Column(DateTime(timezone=True), server_default=func.now())