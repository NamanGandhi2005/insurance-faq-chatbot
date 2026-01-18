# backend/scripts/test_strict_features.py
import sys
import os
import time

# 1. Setup Paths so we can import 'app'
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.dirname(script_dir)
sys.path.append(backend_path)

from app.services.cache_service import CacheService
from app.utils.language_detector import detect_language
from app.database.connection import engine
from sqlalchemy import inspect

def test_language_detection():
    print("\n--- 1. Testing Language Detection (utils/language_detector.py) ---")
    texts = [
        ("Hello, how are you?", "en"),
        ("नमस्ते आप कैसे हैं", "hi"), # Hindi
        ("Comment allez-vous?", "fr"), # French
        ("invalid123 text...", "en")  # Fallback check
    ]
    
    for text, expected in texts:
        result = detect_language(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} Text: '{text[:20]}...' -> Detected: {result} (Expected: {expected})")

def test_strict_caching():
    print("\n--- 2. Testing Strict Caching (services/cache_service.py) ---")
    cache = CacheService()
    
    if not cache.enabled:
        print("❌ Redis is not connected. Skipping cache test.")
        return

    # Test Data matches Guide Section 5.2
    product_id = "health_premium"
    language = "en"
    question = "What is the waiting period?"
    answer = "The waiting period is 30 days."
    sources = ["doc_1_chunk_5"]

    print(f"Storing: Product='{product_id}', Lang='{language}', Q='{question}'")
    
    # Set Cache
    cache.set_qa_cache(product_id, language, question, answer, sources)
    
    # Retrieve Cache
    cached_data = cache.get_qa_cache(product_id, language, question)
    
    if cached_data:
        print(f"✅ Cache Hit! Retrieved Answer: '{cached_data['answer']}'")
        
        # Verify internal key structure (Advanced check)
        key = cache._generate_qa_key(product_id, language, question)
        print(f"   Internal Redis Key: {key}")
    else:
        print("❌ Cache Miss (Something went wrong)")

def test_database_tables():
    print("\n--- 3. Testing Database Schema (models/faq.py, user_product_access.py) ---")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = ["faqs", "user_product_access", "users", "products"]
    
    for table in required_tables:
        if table in tables:
            print(f"✅ Table '{table}' exists.")
        else:
            print(f"❌ Table '{table}' MISSING. Did you restart the server?")

if __name__ == "__main__":
    print("=== STARTING SYSTEM CHECK ===")
    test_language_detection()
    test_strict_caching()
    test_database_tables()
    print("\n=== CHECK COMPLETE ===")