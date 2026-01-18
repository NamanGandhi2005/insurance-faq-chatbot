# app/api/routes/chat.py
import time
import json
import re
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
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

# --- SCHEMAS ---

class ChatRequest(BaseModel):
    product_id: str | None = None
    session_id: str | None = None
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

# --- HELPER: AUDIT LOGGING ---
def _log_audit(db: Session, question: str, answer: str, lang: str, time_ms: float, cached: bool, debug_note: str):
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

# --- ROUTES ---

@router.get("/suggestions", response_model=SuggestionResponse)
def get_chat_suggestions():
    vector_service = VectorDBService()
    questions = vector_service.get_all_cached_questions(limit=10)
    return SuggestionResponse(questions=questions)

# ----------------------------------------------------
# 1. STANDARD BLOCKING ENDPOINT (/ask)
# ----------------------------------------------------
@router.post("/ask", response_model=ChatResponse)
@limiter.limit("10/minute") 
async def ask_question(
    request: Request,
    body: ChatRequest, 
    db: Session = Depends(get_db)
):
    start_time = time.time()
    
    # 1. SETUP
    detected_lang = body.language if body.language and body.language != "auto" else detect_language(body.question)
    product_context = body.product_id if body.product_id else "global"
    session_id = body.session_id if body.session_id else f"temp_{int(time.time())}"

    cache_service = CacheService()
    embed_service = EmbeddingService()
    vector_service = VectorDBService()
    llm_service = LLMService()

    # 2. CONTEXTUALIZATION (HISTORY)
    history = cache_service.get_history(session_id)
    search_query = llm_service.contextualize_query(history, body.question)

    # 3. LAYER 0: MANUAL FAQ
    if body.product_id and body.product_id.isdigit():
        manual_faq = db.query(FAQ).filter(
            FAQ.product_id == int(body.product_id),
            func.lower(FAQ.question) == body.question.lower().strip()
        ).first()
        
        if manual_faq:
            elapsed = time.time() - start_time
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", manual_faq.answer)
            _log_audit(db, body.question, manual_faq.answer, detected_lang, elapsed, True, "Manual FAQ Hit")
            return ChatResponse(
                answer=manual_faq.answer, sources=["Official FAQ"], response_time=elapsed,
                cached=True, detected_language=detected_lang, debug_info="Layer 0: Manual FAQ Hit"
            )

    # 4. LAYER 1: REDIS CACHE
    redis_data = cache_service.get_qa_cache(product_context, detected_lang, search_query)
    if redis_data:
        elapsed = time.time() - start_time
        cache_service.add_to_history(session_id, "user", body.question)
        cache_service.add_to_history(session_id, "assistant", redis_data["answer"])
        _log_audit(db, search_query, redis_data["answer"], detected_lang, elapsed, True, "Redis Hit")
        return ChatResponse(
            answer=redis_data["answer"], sources=redis_data["sources"], response_time=elapsed,
            cached=True, detected_language=detected_lang, debug_info="Layer 1: Redis Hit"
        )

    # 5. LAYER 2: SEMANTIC CACHE
    query_emb = embed_service.generate_embedding(search_query)
    has_numbers = bool(re.search(r'\d', search_query))
    has_history = len(history) > 0 
    
    if not has_numbers and not has_history:
        semantic_hit = vector_service.search_cache(query_emb, threshold=0.20)
        if semantic_hit:
            elapsed = time.time() - start_time
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", semantic_hit["answer"])
            cache_service.set_qa_cache(product_context, detected_lang, search_query, semantic_hit["answer"], semantic_hit["sources"])
            _log_audit(db, search_query, semantic_hit["answer"], detected_lang, elapsed, True, "Semantic Hit")
            return ChatResponse(
                answer=semantic_hit["answer"], sources=semantic_hit["sources"], response_time=elapsed,
                cached=True, detected_language=detected_lang, debug_info="Layer 2: Semantic Hit"
            )

    # 6. LAYER 3: RAG PIPELINE
    # Smart Filtering: Fetch 10, filter out garbage
    search_results = vector_service.search(query_emb, n_results=10)
    
    if not search_results['documents'] or not search_results['documents'][0]:
        elapsed = time.time() - start_time
        _log_audit(db, search_query, "No info found", detected_lang, elapsed, False, "Empty Search")
        return ChatResponse(
            answer="I couldn't find relevant information in any of our policies.", sources=[],
            response_time=elapsed, cached=False, detected_language=detected_lang, debug_info="Layer 3: No Documents Found"
        )
    
    # Filter Logic
    raw_chunks = search_results['documents'][0]
    raw_metas = search_results['metadatas'][0]
    final_chunks, final_metas = [], []
    
    for i, chunk in enumerate(raw_chunks):
        if "Disclaimer" in chunk or "Regd. Office" in chunk or "(cid:" in chunk: continue
        final_chunks.append(chunk)
        final_metas.append(raw_metas[i])
        if len(final_chunks) == 2: break
    
    if not final_chunks: 
        final_chunks = raw_chunks[:2]
        final_metas = raw_metas[:2]

    # Generate Answer
    answer = llm_service.generate_answer(
        question=search_query, 
        context_chunks=final_chunks, 
        metadatas=final_metas, 
        language=detected_lang, 
        history=history
    )
    elapsed = time.time() - start_time

    # 7. CACHE & HISTORY SAVE
    error_phrases = ["I apologize", "Error generating", "internal error"]
    is_error = any(phrase in answer for phrase in error_phrases)
    log_status = "LLM Generated"

    if not is_error:
        cache_service.set_qa_cache(product_context, detected_lang, search_query, answer, final_chunks)
        vector_service.cache_answer(search_query, answer, final_chunks, query_emb)
        cache_service.add_to_history(session_id, "user", body.question)
        cache_service.add_to_history(session_id, "assistant", answer)
    else:
        log_status = "LLM Error (Not Cached)"

    _log_audit(db, search_query, answer, detected_lang, elapsed, False, log_status)
    
    return ChatResponse(
        answer=answer, sources=final_chunks, response_time=elapsed, cached=False,
        detected_language=detected_lang, debug_info=f"Layer 3: {log_status}"
    )

# ----------------------------------------------------
# 2. STREAMING ENDPOINT (/ask_stream)
# ----------------------------------------------------
@router.post("/ask_stream")
@limiter.limit("10/minute") 
async def ask_question_stream(
    request: Request,
    body: ChatRequest, 
    db: Session = Depends(get_db)
):
    start_time = time.time()
    
    detected_lang = body.language if body.language and body.language != "auto" else detect_language(body.question)
    product_context = body.product_id if body.product_id else "global"
    session_id = body.session_id if body.session_id else f"temp_{int(time.time())}"

    cache_service = CacheService()
    embed_service = EmbeddingService()
    vector_service = VectorDBService()
    llm_service = LLMService()

    history = cache_service.get_history(session_id)
    search_query = llm_service.contextualize_query(history, body.question)

    async def response_generator():
        nonlocal start_time
        cached_answer = None
        source_info = []
        debug_msg = ""

        # Layer 0: Manual FAQ
        if body.product_id and body.product_id.isdigit():
            manual_faq = db.query(FAQ).filter(
                FAQ.product_id == int(body.product_id), 
                func.lower(FAQ.question) == body.question.lower().strip()
            ).first()
            if manual_faq:
                cached_answer = manual_faq.answer; source_info = ["Official FAQ"]; debug_msg = "Layer 0: Manual FAQ"

        # Layer 1: Redis
        if not cached_answer:
            redis_data = cache_service.get_qa_cache(product_context, detected_lang, search_query)
            if redis_data:
                cached_answer = redis_data["answer"]; source_info = redis_data["sources"]; debug_msg = "Layer 1: Redis Hit"

        # Layer 2: Semantic
        if not cached_answer:
            has_numbers = bool(re.search(r'\d', search_query))
            has_history = len(history) > 0 
            if not has_numbers and not has_history:
                query_emb = embed_service.generate_embedding(search_query)
                semantic_hit = vector_service.search_cache(query_emb, threshold=0.20)
                if semantic_hit:
                    cached_answer = semantic_hit["answer"]; source_info = semantic_hit["sources"]; debug_msg = "Layer 2: Semantic Hit"

        # IF HIT: Stream simulated
        if cached_answer:
            yield json.dumps({"type": "meta", "sources": source_info, "debug": debug_msg}) + "\n"
            tokens = re.split(r'(\s+)', cached_answer)
            for token in tokens:
                yield json.dumps({"type": "token", "content": token}) + "\n"
                time.sleep(0.01)
            
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", cached_answer)
            _log_audit(db, search_query, cached_answer, detected_lang, (time.time()-start_time), True, debug_msg)
            return

        # IF MISS: LLM Stream
        query_emb = embed_service.generate_embedding(search_query)
        # Smart Filtering
        search_results = vector_service.search(query_emb, n_results=10)
        
        if not search_results['documents'] or not search_results['documents'][0]:
            yield json.dumps({"type": "error", "content": "No info found."}) + "\n"
            return

        raw_chunks = search_results['documents'][0]
        raw_metas = search_results['metadatas'][0]
        final_chunks, final_metas = [], []
        
        for i, chunk in enumerate(raw_chunks):
            if "Disclaimer" in chunk or "Regd. Office" in chunk or "(cid:" in chunk: continue
            final_chunks.append(chunk)
            final_metas.append(raw_metas[i])
            if len(final_chunks) == 2: break
        
        if not final_chunks: 
            final_chunks = raw_chunks[:2]
            final_metas = raw_metas[:2]

        yield json.dumps({"type": "meta", "sources": final_chunks, "debug": "Layer 3: Streaming"}) + "\n"

        full_response = ""
        try:
            stream = llm_service.stream_answer(search_query, final_chunks, final_metas, detected_lang, history)
            for token in stream:
                full_response += token
                yield json.dumps({"type": "token", "content": token}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": "Generation failed."}) + "\n"
            print(f"Stream Error: {e}")
            return

        # Post-Processing
        elapsed = time.time() - start_time
        error_phrases = ["I apologize", "Error generating"]
        if not any(x in full_response for x in error_phrases):
            cache_service.set_qa_cache(product_context, detected_lang, search_query, full_response, final_chunks)
            vector_service.cache_answer(search_query, full_response, final_chunks, query_emb)
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", full_response)
            
        _log_audit(db, search_query, full_response, detected_lang, elapsed, False, "Layer 3: Streamed")

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")