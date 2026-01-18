# app/services/startup_processor.py
import os
import json
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Product, PDFDocument
from app.services.pdf_processor import PDFProcessor
from app.services.embedding_service import EmbeddingService
from app.services.vector_db import VectorDBService

def run_startup_processing(db: Session):
    preload_dir = settings.PDF_PRELOAD_DIR
    mapping_file = os.path.join(preload_dir, "product_mapping.json")
    
    if not os.path.exists(mapping_file):
        print(f"Startup: No product_mapping.json found in {preload_dir}. Skipping.")
        return

    print("--- Running Startup PDF Processing ---")
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)

    for product_key, data in mapping.items():
        product_name = data["product_name"]
        
        # 1. Ensure Product Exists in DB
        product = db.query(Product).filter(Product.name == product_name).first()
        if not product:
            print(f"Creating product: {product_name}")
            product = Product(name=product_name, description="Pre-loaded product")
            db.add(product)
            db.commit()
            db.refresh(product)

        # 2. Process PDFs
        for pdf_entry in data["pdfs"]:
            relative_path = pdf_entry["file"]
            full_path = os.path.join(preload_dir, relative_path)
            
            if not os.path.exists(full_path):
                print(f"Warning: File not found {full_path}")
                continue

            # Check if already processed (simple check by filename)
            existing_pdf = db.query(PDFDocument).filter(
                PDFDocument.product_id == product.id,
                PDFDocument.file_name == os.path.basename(full_path)
            ).first()

            if existing_pdf and existing_pdf.status == "completed":
                print(f"Skipping {relative_path} (Already processed)")
                continue

            print(f"Processing {relative_path}...")
            
            # --- Processing Logic (Copy of Admin Logic) ---
            processor = PDFProcessor()
            text = processor.extract_text(full_path)
            chunks = processor.create_chunks(text, {"source": os.path.basename(full_path)})
            
            embed_service = EmbeddingService()
            texts = [c["text"] for c in chunks]
            embeddings = embed_service.generate_batch_embeddings(texts)
            
            vector_service = VectorDBService()
            ids = [f"{product_name}_{product.id}_{i}_pre" for i in range(len(chunks))]
            metadatas = [c["metadata"] for c in chunks]
            
            vector_service.add_documents(product_name, texts, metadatas, ids, embeddings)
            # ----------------------------------------------

            # Create/Update DB Record
            if not existing_pdf:
                new_pdf = PDFDocument(
                    product_id=product.id,
                    file_name=os.path.basename(full_path),
                    file_path=full_path,
                    file_size=os.path.getsize(full_path),
                    status="completed",
                    chunk_count=len(chunks)
                )
                db.add(new_pdf)
            else:
                existing_pdf.status = "completed"
            
            db.commit()
            print(f"Done: {relative_path}")