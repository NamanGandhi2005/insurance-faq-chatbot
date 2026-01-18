# backend/scripts/test_ingestion.py
import sys
import os

# Add parent dir to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pdf_processor import PDFProcessor
from app.services.embedding_service import EmbeddingService
from app.services.vector_db import VectorDBService

def test_pipeline():
    # 1. Setup
    pdf_path = "../data/pdfs/preload/test.pdf" # Make sure this file exists!
    product_id = "test_product_1"
    
    print("--- Starting Pipeline Test ---")
    
    # 2. Extract & Chunk
    processor = PDFProcessor()
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} not found. Please put a PDF there.")
        return

    print("Extracting text...")
    text = processor.extract_text(pdf_path)
    print(f"Extracted {len(text)} characters.")
    
    chunks = processor.create_chunks(text, {"source": "test.pdf"})
    print(f"Created {len(chunks)} chunks.")
    
    # 3. Embed
    print("Generating embeddings (this downloads the model on first run)...")
    embed_service = EmbeddingService()
    
    texts = [c["text"] for c in chunks]
    embeddings = embed_service.generate_batch_embeddings(texts)
    print(f"Generated {len(embeddings)} vectors.")
    
    # 4. Store
    print("Storing in Vector DB...")
    vector_db = VectorDBService()
    
    ids = [f"{product_id}_{i}" for i in range(len(chunks))]
    metadatas = [c["metadata"] for c in chunks]
    
    vector_db.add_documents(
        product_id=product_id,
        documents=texts,
        metadatas=metadatas,
        ids=ids,
        embeddings=embeddings
    )
    print("Storage complete.")
    
    # 5. Search Verification
    print("Testing Search...")
    query = "What is the insurance coverage?"
    query_emb = embed_service.generate_embedding(query)
    results = vector_db.search(product_id, query_emb)
    
    print("\nSearch Results:")
    print(results['documents'][0])
    print("--- Test Complete ---")

if __name__ == "__main__":
    test_pipeline()