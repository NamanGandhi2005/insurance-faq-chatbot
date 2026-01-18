# app/services/cache_service.py
import redis
import json
import hashlib
from app.config import settings

class CacheService:
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=1
            )
            self.redis.ping() # Check connection
            self.enabled = True
        except redis.ConnectionError:
            print("Warning: Redis not connected. Caching disabled.")
            self.enabled = False

    # ==========================================
    # 1. QA CACHE (Layer 1 - Exact Match)
    # ==========================================

    def _generate_qa_key(self, product_id: str, language: str, question: str) -> str:
        """
        Generates strict key format per Guide Section 5.2:
        faq:qa:{product_id}:{language}:{question_hash}
        """
        # Clean inputs
        pid = str(product_id).lower().strip() if product_id else "global"
        lang = language.lower().strip() if language else "en"
        q_clean = question.strip().lower()
        
        # Hash the question to ensure safe key characters and fixed length
        q_hash = hashlib.md5(q_clean.encode()).hexdigest()
        
        return f"faq:qa:{pid}:{lang}:{q_hash}"

    def get_qa_cache(self, product_id: str, language: str, question: str):
        """Retrieve Exact Match from Redis (Layer 1)"""
        if not self.enabled: return None
        
        key = self._generate_qa_key(product_id, language, question)
        data = self.redis.get(key)
        
        if data:
            return json.loads(data)
        return None

    def set_qa_cache(self, product_id: str, language: str, question: str, answer: str, sources: list):
        """Store Exact Match in Redis (Layer 1)"""
        if not self.enabled: return
        
        key = self._generate_qa_key(product_id, language, question)
        
        payload = {
            "answer": answer,
            "sources": sources,
            "timestamp": str(settings.APP_NAME) # Tracking metadata
        }
        
        # TTL: 24 hours (86400 seconds) per Section 5.2
        self.redis.setex(key, 86400, json.dumps(payload))

    # ==========================================
    # 2. CONVERSATIONAL MEMORY (Session History)
    # ==========================================

    def add_to_history(self, session_id: str, role: str, content: str):
        """
        Stores message in a Redis List: chat:history:{session_id}
        """
        if not self.enabled or not session_id: return
        
        key = f"chat:history:{session_id}"
        message = json.dumps({"role": role, "content": content})
        
        # Push to the end of the list
        self.redis.rpush(key, message)
        
        # Limit history to last 6 messages (3 user + 3 bot) to save LLM context window
        if self.redis.llen(key) > 6:
            self.redis.lpop(key)
            
        # Set expiry to 1 hour so inactive sessions get cleaned up automatically
        self.redis.expire(key, 3600)

    def get_history(self, session_id: str) -> list:
        """
        Returns list of dicts: [{'role': 'user', 'content': '...'}, ...]
        """
        if not self.enabled or not session_id: return []
        
        key = f"chat:history:{session_id}"
        # Get all items in the list (0 to -1)
        raw_history = self.redis.lrange(key, 0, -1)
        
        return [json.loads(item) for item in raw_history]

    # ==========================================
    # 3. UTILITIES
    # ==========================================

    def clear_all(self):
        """Wipes everything in Redis"""
        if self.enabled:
            self.redis.flushdb()