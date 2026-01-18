import time
import json
import re
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.services.embedding_service import EmbeddingService
from app.services.vector_db import VectorDBService
from app.services.llm_service import LLMService
from app.services.cache_service import CacheService
from app.models.audit import AuditLog
from app.models.faq import FAQ
from app.utils.limiter import limiter
from app.utils.language_detector import detect_language

router = APIRouter()

# --- Schemas ---

class ChatRequest(BaseModel):
    product_id: str | None = None
    session_id: str | None = None  # Crucial for memory
    question: str
    language: str | None = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    response_time: float
    cached: bool
    detected_language: str
    debug_info: str | None = None

class SuggestionResponse(BaseModel):
    questions: list[str]

# --- Helper ---
def _log_audit(db, question, answer, lang, time_ms, cached, debug_note):
    try:
        log = AuditLog(
            question=question, 
            answer=answer[:5000], 
            language=lang, 
            response_time_ms=time_ms, 
            is_cached=cached, 
            sources=debug_note
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Audit Log Error: {e}")

# --- Routes ---

@router.get("/suggestions", response_model=SuggestionResponse)
def get_chat_suggestions():
    vector_service = VectorDBService()
    questions = vector_service.get_all_cached_questions(limit=10)
    return SuggestionResponse(questions=questions)

@router.post("/ask", response_model=ChatResponse)
@limiter.limit("10/minute") 
async def ask_question(
    request: Request,
    body: ChatRequest, 
    db: Session = Depends(get_db)
):
    start_time = time.time()
    
    # 1. INITIAL SETUP
    # ----------------
    # Detect language
    detected_lang = body.language if body.language and body.language != "auto" else detect_language(body.question)
    
    # Context & Session
    product_context = body.product_id if body.product_id else "global"
    session_id = body.session_id if body.session_id else "temp_session"

    # Init Services
    cache_service = CacheService()
    embed_service = EmbeddingService()
    vector_service = VectorDBService()
    llm_service = LLMService()

    # 2. CONTEXTUALIZATION (HISTORY)
    # ------------------------------
    # Retrieve previous chat history for this session
    history = cache_service.get_history(session_id)
    
    # Rewrite the question if necessary (e.g., "What about 40 lakhs?" -> "What is sum insured for 40 lakhs?")
    # This 'search_query' will be used for Vector Search and Caching to ensure uniqueness.
    search_query = llm_service.contextualize_query(history, body.question)

    # 3. LAYER 0: MANUAL FAQ (Database Check)
    # ---------------------------------------
    # We check the ORIGINAL question against the DB for exact matches on keywords
    if body.product_id and body.product_id.isdigit():
        manual_faq = db.query(FAQ).filter(
            FAQ.product_id == int(body.product_id),
            func.lower(FAQ.question) == body.question.lower().strip()
        ).first()
        
        if manual_faq:
            elapsed = time.time() - start_time
            # Update History
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", manual_faq.answer)
            
            _log_audit(db, body.question, manual_faq.answer, detected_lang, elapsed, True, "Manual FAQ Hit")
            return ChatResponse(
                answer=manual_faq.answer, sources=["Official FAQ"], response_time=elapsed,
                cached=True, detected_language=detected_lang, debug_info="Layer 0: Manual FAQ Hit"
            )

    # 4. LAYER 1: REDIS CACHE (Exact Match)
    # -------------------------------------
    # Use 'search_query' (rewritten) for the cache key so "it" and "sum insured" hit the same key
    redis_data = cache_service.get_qa_cache(product_context, detected_lang, search_query)
    
    if redis_data:
        elapsed = time.time() - start_time
        # Update History even on cache hit so the next question has context
        cache_service.add_to_history(session_id, "user", body.question)
        cache_service.add_to_history(session_id, "assistant", redis_data["answer"])
        
        _log_audit(db, search_query, redis_data["answer"], detected_lang, elapsed, True, "Redis Hit")
        return ChatResponse(
            answer=redis_data["answer"], sources=redis_data["sources"], response_time=elapsed,
            cached=True, detected_language=detected_lang, debug_info="Layer 1: Redis Exact Hit"
        )

    # 5. LAYER 2: SEMANTIC CACHE (Vector Match)
    # -----------------------------------------
    query_emb = embed_service.generate_embedding(search_query)
    
    # NUMBER & HISTORY SAFETY CHECK: 
    # 1. If question has numbers (20 lakhs), it needs calculation -> Skip Cache
    # 2. If we have chat history, it's a follow-up -> Skip Cache to ensure we read specific PDF sections
    has_numbers = bool(re.search(r'\d', search_query))
    has_history = len(history) > 0 
    
    # Only check Semantic Cache if it's the START of a conversation and no numbers
    if not has_numbers and not has_history:
        semantic_hit = vector_service.search_cache(query_emb, threshold=0.20)
        
        if semantic_hit:
            elapsed = time.time() - start_time
            # Update History
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", semantic_hit["answer"])
            
            # Promote to Redis
            cache_service.set_qa_cache(product_context, detected_lang, search_query, semantic_hit["answer"], semantic_hit["sources"])
            
            _log_audit(db, search_query, semantic_hit["answer"], detected_lang, elapsed, True, "Semantic Hit")
            return ChatResponse(
                answer=semantic_hit["answer"], sources=semantic_hit["sources"], response_time=elapsed,
                cached=True, detected_language=detected_lang, debug_info=f"Layer 2: Semantic Hit"
            )
    # 6. LAYER 3: RAG PIPELINE (Deep Search)
    # --------------------------------------
    # Use n_results=2 for Hardware Optimization
    search_results = vector_service.search(query_emb, n_results=2)
    
    if not search_results['documents'] or not search_results['documents'][0]:
        elapsed = time.time() - start_time
        _log_audit(db, search_query, "No info found", detected_lang, elapsed, False, "Empty Search")
        return ChatResponse(
            answer="I couldn't find relevant information in any of our policies.", sources=[],
            response_time=elapsed, cached=False, detected_language=detected_lang, debug_info="Layer 3: No Documents Found"
        )
        
    chunks = search_results['documents'][0]
    metadatas = search_results['metadatas'][0] 
    
    # Generate Answer
    # CRITICAL: Passing 'history' here enables memory
    answer = llm_service.generate_answer(
        question=search_query, 
        context_chunks=chunks, 
        metadatas=metadatas, 
        language=detected_lang, 
        history=history
    )
    elapsed = time.time() - start_time

    # 7. CACHE & HISTORY SAVE
    # -----------------------
    error_phrases = ["I apologize", "Error generating", "internal error"]
    is_error = any(phrase in answer for phrase in error_phrases)
    log_status = "LLM Generated"

    if not is_error:
        # Save to Redis & Chroma
        cache_service.set_qa_cache(product_context, detected_lang, search_query, answer, chunks)
        vector_service.cache_answer(search_query, answer, chunks, query_emb)
        
        # Add to history
        cache_service.add_to_history(session_id, "user", body.question)
        cache_service.add_to_history(session_id, "assistant", answer)
    else:
        log_status = "LLM Error (Not Cached)"

    _log_audit(db, search_query, answer, detected_lang, elapsed, False, log_status)
    
    return ChatResponse(
        answer=answer, sources=chunks, response_time=elapsed, cached=False,
        detected_language=detected_lang, debug_info=f"Layer 3: {log_status}"
    )