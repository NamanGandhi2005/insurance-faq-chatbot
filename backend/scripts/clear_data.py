# backend/scripts/clear_data.py
import sys
import os
import shutil

# --- Path Setup ---
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.dirname(script_dir)
sys.path.append(backend_path)

# --- Database & Model Imports ---
from app.database.connection import SessionLocal
from app.models.product import Product
from app.models.product import PDFDocument

# --- File Paths ---
UPLOADS_DIR = os.path.join(backend_path, "../data/pdfs/uploads")
PRELOAD_DIR = os.path.join(backend_path, "../data/pdfs/preload")

def clear_database_tables():
    """Deletes all records from the Product and PDFDocument tables."""
    print("--- Clearing Database Tables ---")
    db = SessionLocal()
    try:
        # Delete all PDF documents first due to foreign key constraints
        num_pdfs_deleted = db.query(PDFDocument).delete()
        print(f"Deleted {num_pdfs_deleted} PDF document records.")

        # Delete all products
        num_products_deleted = db.query(Product).delete()
        print(f"Deleted {num_products_deleted} product records.")

        db.commit()
        print("--- Database tables cleared successfully. ---")
    except Exception as e:
        print(f"An error occurred while clearing the database: {e}")
        db.rollback()
    finally:
        db.close()

def clear_pdf_files():
    """Deletes all PDF files from the upload and preload directories."""
    print("\n--- Clearing PDF Files ---")
    
    # Clear uploads directory
    if os.path.exists(UPLOADS_DIR):
        for item in os.listdir(UPLOADS_DIR):
            item_path = os.path.join(UPLOADS_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"Deleted directory: {item_path}")
    else:
        print(f"Uploads directory not found: {UPLOADS_DIR}")

    # Clear preload directory (optional: you might want to keep some files)
    if os.path.exists(PRELOAD_DIR):
        for item in os.listdir(PRELOAD_DIR):
            if item.lower().endswith(".pdf") and item.lower() != "test.pdf":
                item_path = os.path.join(PRELOAD_DIR, item)
                os.remove(item_path)
                print(f"Deleted file: {item_path}")
    else:
        print(f"Preload directory not found: {PRELOAD_DIR}")
        
    print("--- PDF files cleared successfully. ---")


if __name__ == "__main__":
    clear_database_tables()
    clear_pdf_files()
    print("\nOperation completed.")
