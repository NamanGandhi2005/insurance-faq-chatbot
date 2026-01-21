# app/services/vector_db.py
import chromadb
import json
import hashlib
from app.config import settings

class VectorDBService:
    def __init__(self):
        # Initialize persistent client
        self.client = chromadb.PersistentClient(path=settings.VECTOR_DB_PATH)

    # ==========================================
    # 1. GLOBAL DOCUMENT SEARCH (RAG)
    # ==========================================

    def get_global_collection(self):
        """Returns the main collection containing chunks from ALL products."""
        return self.client.get_or_create_collection(name="all_products")

    def add_documents(self, product_name: str, documents: list, metadatas: list, ids: list, embeddings: list):
        """Stores document chunks with product_name in metadata."""
        collection = self.get_global_collection()

        # Normalize product name (title case) for consistent filtering
        normalized_name = product_name.strip().title()

        # Inject Product Name into metadata so the LLM knows which policy is which
        enhanced_metadatas = []
        for meta in metadatas:
            new_meta = meta.copy()
            new_meta["product_name"] = normalized_name
            # Ensure all metadata values are primitives (str, int, float, bool) for ChromaDB
            # If 'source' is missing, add it
            if "source" not in new_meta:
                new_meta["source"] = "Unknown File"
            enhanced_metadatas.append(new_meta)

        collection.upsert(
            documents=documents,
            metadatas=enhanced_metadatas,
            ids=ids,
            embeddings=embeddings
        )

    def search(self, query_embedding: list, n_results: int = 15, product_filter: str = None):
        """
        Searches the global collection. 
        If product_filter is provided (e.g. "Care Supreme"), it restricts search to that product.
        """
        collection = self.get_global_collection()
        
        # Prepare filter dict if provided
        where_clause = {"product_name": product_filter} if product_filter else None
        
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_clause  # <--- CRITICAL ADDITION
        )

    # ==========================================
    # 2. SEMANTIC CACHING
    # ==========================================

    def get_cache_collection(self):
        """Returns the collection used for storing Q&A pairs."""
        return self.client.get_or_create_collection(name="semantic_cache")

    def cache_answer(self, question: str, answer: str, sources: list, embedding: list):
        """Stores a generated answer and question embedding in the cache."""
        collection = self.get_cache_collection()
        
        # Create a deterministic ID based on the question text
        q_hash = hashlib.md5(question.strip().lower().encode()).hexdigest()
        
        # Prepare metadata
        # Note: ChromaDB metadata cannot store lists, so we dump 'sources' to a JSON string
        metadata = {
            "answer": answer,
            "sources": json.dumps(sources), 
            "original_question": question
        }
        
        collection.upsert(
            ids=[q_hash],
            embeddings=[embedding],
            documents=[question],
            metadatas=[metadata]
        )

        def clear_semantic_cache(self):
        
            try:
                self.client.delete_collection(name="semantic_cache")
            except ValueError:
                pass # Collection didn't exist, ignore error
                
            # Recreate it immediately so it is ready for new writes
            self.get_cache_collection()

    def search_cache(self, query_embedding: list, threshold: float = 0.35):
        """
        Searches for a similar question in the cache.
        
        Args:
            query_embedding: The vector of the user's current question.
            threshold: Similarity cutoff. Lower = Stricter match. 
                       0.0 = Identical, 0.3-0.4 = Semantically similar.
        """
        collection = self.get_cache_collection()
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=1 # We only need the best match
        )
        
        # If cache is empty or no results
        if not results['ids'] or not results['ids'][0]:
            return None

        # Check the distance (Cosine distance: 0 is identical, 2 is opposite)
        distance = results['distances'][0][0]
        
        if distance < threshold:
            metadata = results['metadatas'][0][0]
            return {
                "answer": metadata["answer"],
                "sources": json.loads(metadata["sources"]), # Convert string back to list
                "distance": distance
            }
        
        return None
    def get_all_cached_questions(self, limit: int = 10):
        """
        Retrieves a list of frequently asked questions from the semantic cache.
        """
        collection = self.get_cache_collection()
        
        # Get the first 'limit' number of entries from the cache
        results = collection.get(limit=limit)
        
        if not results or not results['documents']:
            return []
            
        return results['documents'] # The 'documents' field holds the actual question text



    def clear_semantic_cache(self):
            """Deletes and recreates the semantic cache collection."""
            try:
                self.client.delete_collection(name="semantic_cache")
            except ValueError:
                pass # Collection didn't exist, ignore
                
            # Recreate it immediately
            self.get_cache_collection()
    def clear_knowledge_base(self):
        """Deletes the main document collection (RAG Data)."""
        try:
            self.client.delete_collection(name="all_products")
        except ValueError:
            pass # Collection didn't exist
        
        # Recreate immediately
        self.get_global_collection()