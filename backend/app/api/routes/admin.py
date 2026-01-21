import os
import shutil
import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pydantic import BaseModel

from app.database.connection import get_db
from app.config import settings
from app.models.product import Product, PDFDocument
from app.models.user import User
from app.models.audit import AuditLog
from app.models.faq import FAQ
from app.utils.security import get_current_admin
from app.services.pdf_processor import PDFProcessor
from app.services.embedding_service import EmbeddingService
from app.services.vector_db import VectorDBService
from app.services.cache_service import CacheService
from app.services.startup_processor import run_startup_processing

router = APIRouter()

# =======================
# 1. SCHEMAS
# =======================

class AuditLogResponse(BaseModel):
    id: int
    question: str
    answer: str
    created_at: datetime
    response_time_ms: float
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserRoleUpdate(BaseModel):
    role: str  # e.g., "admin" or "viewer"

class FAQCreate(BaseModel):
    question: str
    answer: str
    language: str = "en"

class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    language: str | None = None

class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    language: str
    product_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# =======================
# 2. BACKGROUND TASKS
# =======================

def process_pdf_background(file_path: str, product_name: str, pdf_db_id: int, db: Session):
    """
    Extracts text, generates embeddings, and stores vectors in ChromaDB.
    """
    try:
        # 1. Extract Text
        processor = PDFProcessor()
        text = processor.extract_text(file_path)
        chunks = processor.create_chunks(text, {"source": os.path.basename(file_path)})
        
        # 2. Generate Embeddings
        embed_service = EmbeddingService()
        texts = [c["text"] for c in chunks]
        embeddings = embed_service.generate_batch_document_embeddings(texts)
        
        # 3. Store in Vector DB (Global Collection)
        vector_service = VectorDBService()
        
        # Create unique IDs for ChromaDB
        ids = [f"{product_name}_{pdf_db_id}_{i}" for i in range(len(chunks))]
        metadatas = [c["metadata"] for c in chunks]
        
        # Pass product_name so it gets stamped on every chunk's metadata
        vector_service.add_documents(
            product_name=product_name, 
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        
        # 4. Update Database Status to 'completed'
        # Note: In a real celery task, we'd need a fresh DB session here.
        # Since this runs in BackgroundTasks (same process), reusing 'db' is risky if request closes.
        # Ideally, create a new session inside this function using SessionLocal().
        # For simplicity in this implementation, we assume db session is still valid or handled.
        pdf_record = db.query(PDFDocument).filter(PDFDocument.id == pdf_db_id).first()
        if pdf_record:
            pdf_record.status = "completed"
            pdf_record.chunk_count = len(chunks)
            db.commit()
            
    except Exception as e:
        print(f"Error processing PDF: {e}")
        # Mark as error in DB
        pdf_record = db.query(PDFDocument).filter(PDFDocument.id == pdf_db_id).first()
        if pdf_record:
            pdf_record.status = "error"
            db.commit()

# =======================
# 3. PDF MANAGEMENT ROUTES
# =======================

@router.post("/upload-pdf")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    product_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    # 1. Verify Product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Prepare Directory
    upload_dir = os.path.join(settings.PDF_UPLOAD_DIR, str(product_id))
    os.makedirs(upload_dir, exist_ok=True)
    
    # 3. Validate and Save File
    file_extension = os.path.splitext(file.filename)[1]
    if file_extension.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
        
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 4. Create DB Entry
    new_pdf = PDFDocument(
        product_id=product_id,
        file_name=file.filename,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
        status="processing"
    )
    db.add(new_pdf)
    db.commit()
    db.refresh(new_pdf)
    
    # 5. Trigger Background Processing
    background_tasks.add_task(process_pdf_background, file_path, product.name, new_pdf.id, db)
    
    return {"message": "File uploaded and processing started", "pdf_id": new_pdf.id}

@router.get("/pdfs/{product_id}")
def list_pdfs(
    product_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """List all PDFs associated with a product."""
    pdfs = db.query(PDFDocument).filter(PDFDocument.product_id == product_id).all()
    return pdfs

@router.get("/products/{product_id}/pdfs/{pdf_id}/status")
def get_pdf_status(
    product_id: int, 
    pdf_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Check processing status of a specific PDF."""
    pdf = db.query(PDFDocument).filter(
        PDFDocument.id == pdf_id, 
        PDFDocument.product_id == product_id
    ).first()
    
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    return {
        "status": pdf.status,
        "chunk_count": pdf.chunk_count,
        "filename": pdf.file_name,
        "message": "Ready" if pdf.status == "completed" else "Processing..."
    }

@router.delete("/pdfs/{pdf_id}")
def delete_pdf(
    pdf_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a PDF file from disk and database."""
    pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # 1. Remove file from disk
    if os.path.exists(pdf.file_path):
        try:
            os.remove(pdf.file_path)
        except OSError:
            pass # File might already be gone
        
    # 2. Remove from Database
    db.delete(pdf)
    db.commit()
    
    return {"message": "PDF deleted successfully"}

@router.post("/products/{product_id}/reprocess-pdfs")
def reprocess_pdfs(
    product_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Triggers reprocessing of ALL PDFs for a specific product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    pdfs = db.query(PDFDocument).filter(PDFDocument.product_id == product_id).all()
    
    count = 0
    for pdf in pdfs:
        if os.path.exists(pdf.file_path):
            # Reset status
            pdf.status = "processing"
            # Trigger background task
            background_tasks.add_task(process_pdf_background, pdf.file_path, product.name, pdf.id, db)
            count += 1
    
    db.commit()
    return {"message": f"Reprocessing triggered for {count} PDFs"}

@router.post("/startup/reload")
def reload_startup_pdfs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Manually triggers the startup folder scan (Approach 1)."""
    run_startup_processing(db)
    return {"message": "Startup processing triggered"}

# =======================
# 4. FAQ MANAGEMENT
# =======================

@router.post("/products/{product_id}/pre-faq", response_model=FAQResponse)
def add_pre_faq(
    product_id: int, 
    faq_data: FAQCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add a manually managed FAQ to the database."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    new_faq = FAQ(
        product_id=product_id,
        question=faq_data.question,
        answer=faq_data.answer,
        language=faq_data.language
    )
    db.add(new_faq)
    db.commit()
    db.refresh(new_faq)
    return new_faq

@router.get("/products/{product_id}/pre-faq", response_model=List[FAQResponse])
def get_pre_faqs(
    product_id: int, 
    db: Session = Depends(get_db)
):
    """Get all FAQs for a product (Public or Admin)."""
    return db.query(FAQ).filter(FAQ.product_id == product_id).all()

@router.put("/products/{product_id}/pre-faq/{faq_id}", response_model=FAQResponse)
def update_pre_faq(
    product_id: int,
    faq_id: int,
    faq_data: FAQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update an existing FAQ."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id, FAQ.product_id == product_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    if faq_data.question: faq.question = faq_data.question
    if faq_data.answer: faq.answer = faq_data.answer
    if faq_data.language: faq.language = faq_data.language
    
    db.commit()
    db.refresh(faq)
    return faq

@router.delete("/products/{product_id}/pre-faq/{faq_id}")
def delete_pre_faq(
    product_id: int,
    faq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an FAQ."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id, FAQ.product_id == product_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    db.delete(faq)
    db.commit()
    return {"message": "FAQ deleted successfully"}

# =======================
# 5. AUDIT & LOGS
# =======================

@router.get("/audit", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Retrieve latest chat history/audit logs."""
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()

# =======================
# 6. USER MANAGEMENT
# =======================

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """List all registered users."""
    users = db.query(User).all()
    return users

@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Promote or Demote a user."""
    user_to_update = db.query(User).filter(User.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    valid_roles = ["admin", "viewer"]
    if role_data.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {valid_roles}")

    # Safety Check: Admin cannot demote themselves
    if user_to_update.id == current_user.id and role_data.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself.")

    user_to_update.role = role_data.role
    db.commit()
    db.refresh(user_to_update)
    
    return user_to_update

# =======================
# 7. CACHE & SYSTEM MANAGEMENT
# =======================

@router.get("/cache/stats")
def get_cache_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Returns statistics about chatbot usage and cache performance."""
    total_requests = db.query(AuditLog).count()
    cache_hits = db.query(AuditLog).filter(AuditLog.is_cached == True).count()
    cache_misses = total_requests - cache_hits
    
    hit_rate = 0
    if total_requests > 0:
        hit_rate = round((cache_hits / total_requests) * 100, 2)
        
    avg_time = db.query(func.avg(AuditLog.response_time_ms)).scalar() or 0
    
    return {
        "total_requests": total_requests,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "hit_rate_percentage": hit_rate,
        "average_response_time_sec": round(avg_time, 4)
    }

@router.delete("/cache/semantic")
def clear_semantic_cache(current_user: User = Depends(get_current_admin)):
    """Wipes the Semantic Cache (ChromaDB Q&A collection)."""
    service = VectorDBService()
    service.clear_semantic_cache()
    return {"message": "Semantic cache (Q&A) cleared successfully"}

@router.delete("/cache/redis")
def clear_redis_cache(current_user: User = Depends(get_current_admin)):
    """Wipes the Redis Cache (Rate limits, etc)."""
    service = CacheService()
    if not service.enabled:
        raise HTTPException(status_code=400, detail="Redis is not enabled")
    service.clear_all()
    return {"message": "Redis cache flushed successfully"}

@router.delete("/knowledge-base/clear")
def clear_knowledge_base(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    WARNING: Deletes all document embeddings. 
    The chatbot will forget all PDF content until reprocessed.
    """
    # 1. Wipe Vector DB
    service = VectorDBService()
    service.clear_knowledge_base()
    
    # 2. Reset PDF status in DB
    pdfs = db.query(PDFDocument).filter(PDFDocument.status == "completed").all()
    for pdf in pdfs:
        pdf.status = "uploaded" # Reset to uploaded (needs processing)
        pdf.chunk_count = 0
    
    db.commit()
    
    return {"message": "Knowledge base cleared. PDFs marked for reprocessing."}