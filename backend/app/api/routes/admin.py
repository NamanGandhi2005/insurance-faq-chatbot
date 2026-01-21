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
from app.utils.encryption import encrypt_id, decrypt_id

router = APIRouter()

# =======================
# 1. SCHEMAS
# =======================

class AuditLogResponse(BaseModel):
    id: str  # Encrypted ID
    question: str
    answer: str
    created_at: datetime
    response_time_ms: float
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str  # Encrypted ID
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
    id: str  # Encrypted ID
    question: str
    answer: str
    language: str
    product_id: str  # Encrypted ID
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
    encrypted_product_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    product_id = decrypt_id(encrypted_product_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Security: Validate content type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are allowed.")

    # Security: Read file with a size limit to prevent large file attacks
    contents = await file.read(settings.MAX_FILE_SIZE + 1)
    if len(contents) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File size exceeds the limit of {settings.MAX_FILE_SIZE // 1024 // 1024}MB.")

    # Security: Check for PDF magic number (%PDF)
    if not contents.startswith(b'%PDF-'):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    upload_dir = os.path.join(settings.PDF_UPLOAD_DIR, str(product_id))
    os.makedirs(upload_dir, exist_ok=True)
    
    unique_filename = f"{uuid.uuid4()}.pdf"
    file_path = os.path.join(upload_dir, unique_filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
        
    new_pdf = PDFDocument(
        product_id=product_id,
        file_name=file.filename,
        file_path=file_path,
        file_size=len(contents),
        status="processing"
    )
    db.add(new_pdf)
    db.commit()
    db.refresh(new_pdf)
    
    background_tasks.add_task(process_pdf_background, file_path, product.name, new_pdf.id, db)
    
    return {"message": "File uploaded and processing started", "pdf_id": encrypt_id(new_pdf.id)}

@router.get("/pdfs/{encrypted_product_id}")
def list_pdfs(
    encrypted_product_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """List all PDFs associated with a product."""
    product_id = decrypt_id(encrypted_product_id)
    pdfs = db.query(PDFDocument).filter(PDFDocument.product_id == product_id).all()
    return pdfs

@router.get("/products/{encrypted_product_id}/pdfs/{encrypted_pdf_id}/status")
def get_pdf_status(
    encrypted_product_id: str, 
    encrypted_pdf_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Check processing status of a specific PDF."""
    product_id = decrypt_id(encrypted_product_id)
    pdf_id = decrypt_id(encrypted_pdf_id)
    
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

@router.delete("/pdfs/{encrypted_pdf_id}")
def delete_pdf(
    encrypted_pdf_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a PDF file from disk and database."""
    pdf_id = decrypt_id(encrypted_pdf_id)
    pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    if os.path.exists(pdf.file_path):
        try:
            os.remove(pdf.file_path)
        except OSError:
            pass
        
    db.delete(pdf)
    db.commit()
    
    return {"message": "PDF deleted successfully"}

@router.post("/products/{encrypted_product_id}/reprocess-pdfs")
def reprocess_pdfs(
    encrypted_product_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Triggers reprocessing of ALL PDFs for a specific product."""
    product_id = decrypt_id(encrypted_product_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    pdfs = db.query(PDFDocument).filter(PDFDocument.product_id == product_id).all()
    
    count = 0
    for pdf in pdfs:
        if os.path.exists(pdf.file_path):
            pdf.status = "processing"
            background_tasks.add_task(process_pdf_background, pdf.file_path, product.name, pdf.id, db)
            count += 1
    
    db.commit()
    return {"message": f"Reprocessing triggered for {count} PDFs"}

# =======================
# 4. FAQ MANAGEMENT
# =======================

@router.post("/products/{encrypted_product_id}/pre-faq", response_model=FAQResponse)
def add_pre_faq(
    encrypted_product_id: str, 
    faq_data: FAQCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add a manually managed FAQ to the database."""
    product_id = decrypt_id(encrypted_product_id)
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
    return FAQResponse(
        id=encrypt_id(new_faq.id),
        question=new_faq.question,
        answer=new_faq.answer,
        language=new_faq.language,
        product_id=encrypt_id(new_faq.product_id),
        created_at=new_faq.created_at
    )

@router.get("/products/{encrypted_product_id}/pre-faq", response_model=List[FAQResponse])
def get_pre_faqs(
    encrypted_product_id: str, 
    db: Session = Depends(get_db)
):
    """Get all FAQs for a product (Public or Admin)."""
    product_id = decrypt_id(encrypted_product_id)
    faqs = db.query(FAQ).filter(FAQ.product_id == product_id).all()
    return [
        FAQResponse(
            id=encrypt_id(f.id),
            question=f.question,
            answer=f.answer,
            language=f.language,
            product_id=encrypt_id(f.product_id),
            created_at=f.created_at
        ) for f in faqs
    ]

@router.put("/products/{encrypted_product_id}/pre-faq/{encrypted_faq_id}", response_model=FAQResponse)
def update_pre_faq(
    encrypted_product_id: str,
    encrypted_faq_id: str,
    faq_data: FAQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update an existing FAQ."""
    product_id = decrypt_id(encrypted_product_id)
    faq_id = decrypt_id(encrypted_faq_id)
    
    faq = db.query(FAQ).filter(FAQ.id == faq_id, FAQ.product_id == product_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    if faq_data.question: faq.question = faq_data.question
    if faq_data.answer: faq.answer = faq_data.answer
    if faq_data.language: faq.language = faq_data.language
    
    db.commit()
    db.refresh(faq)
    return FAQResponse(
        id=encrypt_id(faq.id),
        question=faq.question,
        answer=faq.answer,
        language=faq.language,
        product_id=encrypt_id(faq.product_id),
        created_at=faq.created_at
    )

@router.delete("/products/{encrypted_product_id}/pre-faq/{encrypted_faq_id}")
def delete_pre_faq(
    encrypted_product_id: str,
    encrypted_faq_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an FAQ."""
    product_id = decrypt_id(encrypted_product_id)
    faq_id = decrypt_id(encrypted_faq_id)
    
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
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        AuditLogResponse(
            id=encrypt_id(log.id),
            question=log.question,
            answer=log.answer,
            created_at=log.created_at,
            response_time_ms=log.response_time_ms
        ) for log in logs
    ]

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
    return [
        UserResponse(
            id=encrypt_id(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at
        ) for user in users
    ]

@router.put("/users/{encrypted_user_id}/role", response_model=UserResponse)
def update_user_role(
    encrypted_user_id: str,
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Promote or Demote a user."""
    user_id = decrypt_id(encrypted_user_id)
    user_to_update = db.query(User).filter(User.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    valid_roles = ["admin", "viewer"]
    if role_data.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {valid_roles}")

    if user_to_update.id == current_user.id and role_data.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself.")

    user_to_update.role = role_data.role
    db.commit()
    db.refresh(user_to_update)
    
    return UserResponse(
        id=encrypt_id(user_to_update.id),
        email=user_to_update.email,
        full_name=user_to_update.full_name,
        role=user_to_update.role,
        is_active=user_to_update.is_active,
        created_at=user_to_update.created_at
    )
    
# Other routes remain the same...
@router.post("/startup/reload")
def reload_startup_pdfs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Manually triggers the startup folder scan (Approach 1)."""
    run_startup_processing(db)
    return {"message": "Startup processing triggered"}

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