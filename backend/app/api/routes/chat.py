# app/api/routes/chat.py
import time
import json
import re
import asyncio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func


from app.models.product import Product
from app.database.connection import get_db
from app.services.embedding_service import EmbeddingService
from app.services.vector_db import VectorDBService
from app.services.llm_service import LLMService
from app.services.cache_service import CacheService
from app.models.audit import AuditLog
from app.models.faq import FAQ
from app.models.product import Product
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
    session_id = body.session_id if body.session_id else f"temp_{int(time.time())}"

    cache_service = CacheService()
    embed_service = EmbeddingService()
    vector_service = VectorDBService()
    llm_service = LLMService()

    # 2. CONTEXTUALIZATION & PRODUCT DETECTION
    history = cache_service.get_history(session_id)
    search_query = llm_service.contextualize_query(history, body.question)

    target_product_name = None
    if body.product_id and body.product_id.isdigit():
        prod = db.query(Product).filter(Product.id == int(body.product_id)).first()
        if prod: target_product_name = prod.name
    
    if not target_product_name:
        all_products = db.query(Product).all()
        for p in all_products:
            if p.name.lower() in search_query.lower():
                target_product_name = p.name; break
    
    product_context = target_product_name or "global"
    
    # 3. INTENT RECOGNITION (Handle "list all plans" type questions)
    summary_keywords = ["various plans", "all plans", "list plans", "compare plans", "types of insurance", "what plans"]
    if any(keyword in search_query.lower() for keyword in summary_keywords):
        all_products = db.query(Product).all()
        if not all_products:
            summary_answer = "I don't have information on any specific plans right now."
        else:
            product_names = [f"'{p.name}'" for p in all_products]
            summary_answer = f"I have information on the following plans: {', '.join(product_names)}. Which one would you like to know more about?"
        
        elapsed = time.time() - start_time
        cache_service.add_to_history(session_id, "user", body.question)
        cache_service.add_to_history(session_id, "assistant", summary_answer)
        _log_audit(db, search_query, summary_answer, detected_lang, elapsed, False, "Summary Intent")
        return ChatResponse(
            answer=summary_answer, sources=["System"], response_time=elapsed, cached=False,
            detected_language=detected_lang, debug_info="Intent: Summary"
        )

    # 4. CACHING LAYERS (0, 1, 2)
    # Layer 0: Manual FAQ
    if body.product_id and body.product_id.isdigit():
        manual_faq = db.query(FAQ).filter(FAQ.product_id == int(body.product_id), func.lower(FAQ.question) == body.question.lower().strip()).first()
        if manual_faq:
            # ... (return cached response)
            pass

    # Layer 1: Redis
    redis_data = cache_service.get_qa_cache(product_context, detected_lang, search_query)
    if redis_data:
        # ... (return cached response)
        pass
    
    # Layer 2: Semantic
    query_emb = embed_service.generate_query_embedding(search_query)
    has_numbers = bool(re.search(r'\d', search_query))
    if not has_numbers and not history:
        semantic_hit = vector_service.search_cache(query_emb, threshold=0.20)
        if semantic_hit:

            # ... (return cached response)
            pass

    # 5. LAYER 3: RAG PIPELINE (WITH RE-RANKING)
    # A. Retrieve Broadly
    search_results = vector_service.search(query_emb, n_results=15, product_filter=target_product_name)

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
    # Filter by product_name if specified, otherwise search all products
    search_results = vector_service.search(query_emb, n_results=2, product_name=product_name)

    
    if not search_results['documents'] or not search_results['documents'][0]:
        elapsed = time.time() - start_time
        _log_audit(db, search_query, "No info found", detected_lang, elapsed, False, "Empty Search")
        return ChatResponse(
            answer="I couldn't find relevant information in any of our policies.", sources=[],
            response_time=elapsed, cached=False, detected_language=detected_lang, debug_info="Layer 3: No Docs"
        )
    
    # B. Keyword Re-Ranking
    raw_chunks = search_results['documents'][0]
    raw_metas = search_results['metadatas'][0]
    keywords = [w.lower() for w in search_query.split() if len(w) > 3]
    
    scored_chunks = []
    for i, chunk in enumerate(raw_chunks):
        score = sum(10 for kw in keywords if kw in chunk.lower())
        if any(char.isdigit() for char in chunk): score += 5
        if "disclaimer" in chunk.lower() or "regd. office" in chunk.lower(): score -= 20
        if "(cid:" in chunk.lower(): score -= 10
        scored_chunks.append({"text": chunk, "meta": raw_metas[i], "score": score, "original_rank": i})
        
    scored_chunks.sort(key=lambda x: (x["score"], -x["original_rank"]), reverse=True)
    
    final_chunks = [x["text"] for x in scored_chunks[:3]]
    final_metas = [x["meta"] for x in scored_chunks[:3]]

    # C. Generate Answer
    answer = llm_service.generate_answer(search_query, final_chunks, final_metas, detected_lang, history)
    elapsed = time.time() - start_time

    # 6. SAVE
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

# Add asyncio to your imports at the top of the file
import asyncio

# ... (keep all other existing imports)

@router.post("/ask_stream")
@limiter.limit("10/minute") 
async def ask_question_stream(
    request: Request,
    body: ChatRequest, 
    db: Session = Depends(get_db)
):
    start_time = time.time()
    
    # 1. SETUP
    detected_lang = body.language if body.language and body.language != "auto" else detect_language(body.question)
    session_id = body.session_id if body.session_id else f"temp_{int(time.time())}"
    cache_service = CacheService(); embed_service = EmbeddingService(); vector_service = VectorDBService(); llm_service = LLMService()

    # 2. CONTEXTUALIZATION & PRODUCT DETECTION
    history = cache_service.get_history(session_id)
    search_query = llm_service.contextualize_query(history, body.question)
    target_product_name = None
    if body.product_id and body.product_id.isdigit():
        prod = db.query(Product).filter(Product.id == int(body.product_id)).first()
        if prod: target_product_name = prod.name
    if not target_product_name:
        all_products = db.query(Product).all()
        for p in all_products:
            if p.name.lower() in search_query.lower():
                target_product_name = p.name; break
    product_context = target_product_name or "global"

    # --- THE GENERATOR FUNCTION THAT CONTAINS THE CORE LOGIC ---
    async def response_generator():
        nonlocal start_time, search_query, history, session_id, product_context, detected_lang, target_product_name
        
        # 3. INTENT RECOGNITION (The Router)
        # ------------------------------------
        # Intent 1: User wants a summary of all plans
        summary_keywords = ["various plans", "all plans", "list plans", "types of insurance", "what plans"]
        if any(keyword in search_query.lower() for keyword in summary_keywords):
            all_products = db.query(Product).all()
            product_names = [f"'{p.name}'" for p in all_products] if all_products else []
            summary_answer = f"I have information on the following plans: {', '.join(product_names)}. Which one would you like to know more about?" if product_names else "I don't have information on any specific plans right now."
            
            yield json.dumps({"type": "meta", "sources": ["System"], "debug": "Intent: Summary"}) + "\n"
            tokens = re.split(r'(\s+)', summary_answer)
            for token in tokens:
                yield json.dumps({"type": "token", "content": token}) + "\n"
                await asyncio.sleep(0.01)
            
            cache_service.add_to_history(session_id, "user", body.question); cache_service.add_to_history(session_id, "assistant", summary_answer)
            _log_audit(db, search_query, summary_answer, detected_lang, (time.time()-start_time), False, "Summary Intent")
            return

        # Intent 2: User wants to compare plans
        comparison_keywords = ["compare", "vs", "versus", "difference between"]
        if any(keyword in search_query.lower() for keyword in comparison_keywords):
            all_products = db.query(Product).all()
            full_text_to_scan = search_query.lower() + " " + " ".join([h['content'].lower() for h in history])
            products_to_compare = list(set([p.name for p in all_products if p.name.lower() in full_text_to_scan]))

            if len(products_to_compare) >= 2:
                final_chunks, final_metas = [], []
                for prod_name in products_to_compare[:2]: # Limit to comparing 2 products for performance
                    comp_query_emb = embed_service.generate_query_embedding(f"Summary of key features for {prod_name}")
                    search_results = vector_service.search(comp_query_emb, n_results=2, product_filter=prod_name)
                    if search_results['documents'] and search_results['documents'][0]:
                        final_chunks.extend(search_results['documents'][0]); final_metas.extend(search_results['metadatas'][0])
                
                if final_chunks:
                    comparison_prompt = f"Based on the documents, create a brief comparison of the key features of the '{products_to_compare[0]}' and '{products_to_compare[1]}' plans."
                    yield json.dumps({"type": "meta", "sources": final_chunks, "debug": f"Intent: Compare"}) + "\n"
                    full_response = ""
                    stream = llm_service.stream_answer(comparison_prompt, final_chunks, final_metas, detected_lang, [])
                    for token in stream:
                        full_response += token
                        yield json.dumps({"type": "token", "content": token}) + "\n"

                    _log_audit(db, search_query, full_response, detected_lang, (time.time()-start_time), False, "Comparison Intent")
                    cache_service.add_to_history(session_id, "user", body.question); cache_service.add_to_history(session_id, "assistant", full_response)
                    return

        # 4. CACHING LAYERS (0, 1, 2)
        # ---------------------------
        cached_answer = None; source_info = []; debug_msg = ""
        # Layer 0: Manual FAQ
        if body.product_id and body.product_id.isdigit():
            manual_faq = db.query(FAQ).filter(FAQ.product_id == int(body.product_id), func.lower(FAQ.question) == body.question.lower().strip()).first()
            if manual_faq: cached_answer, source_info, debug_msg = manual_faq.answer, ["Official FAQ"], "Layer 0: Manual FAQ"

        # Layer 1: Redis
        if not cached_answer:
            redis_data = cache_service.get_qa_cache(product_context, detected_lang, search_query)
            if redis_data: cached_answer, source_info, debug_msg = redis_data["answer"], redis_data["sources"], "Layer 1: Redis Hit"

        # Layer 2: Semantic
        if not cached_answer:
            has_numbers = bool(re.search(r'\d', search_query))
            if not has_numbers and not history:
                query_emb = embed_service.generate_query_embedding(search_query)
                semantic_hit = vector_service.search_cache(query_emb, threshold=0.20)
                if semantic_hit: cached_answer, source_info, debug_msg = semantic_hit["answer"], semantic_hit["sources"], "Layer 2: Semantic Hit"
        
        # IF CACHE HIT: Stream it quickly
        if cached_answer:
            yield json.dumps({"type": "meta", "sources": source_info, "debug": debug_msg}) + "\n"
            tokens = re.split(r'(\s+)', cached_answer)
            for token in tokens:
                yield json.dumps({"type": "token", "content": token}) + "\n"
                await asyncio.sleep(0.01)
            
            cache_service.add_to_history(session_id, "user", body.question); cache_service.add_to_history(session_id, "assistant", cached_answer)
            _log_audit(db, search_query, cached_answer, detected_lang, (time.time()-start_time), True, debug_msg)
            return

        # 5. RAG PIPELINE (Layer 3)
        # -------------------------
        query_emb = embed_service.generate_query_embedding(search_query)
        search_results = vector_service.search(query_emb, n_results=15, product_filter=target_product_name)
        
        if not search_results['documents'] or not search_results['documents'][0]:
            yield json.dumps({"type": "error", "content": "No relevant documents found."}) + "\n"; return

        raw_chunks, raw_metas = search_results['documents'][0], search_results['metadatas'][0]
        keywords = [w.lower() for w in search_query.split() if len(w) > 3]
        scored_chunks = []
        for i, chunk in enumerate(raw_chunks):
            score = sum(10 for kw in keywords if kw in chunk.lower())
            if any(char.isdigit() for char in chunk): score += 5
            if "disclaimer" in chunk.lower() or "regd. office" in chunk.lower(): score -= 20
            if "(cid:" in chunk.lower(): score -= 10
            scored_chunks.append({"text": chunk, "meta": raw_metas[i], "score": score, "original_rank": i})
        scored_chunks.sort(key=lambda x: (x["score"], -x["original_rank"]), reverse=True)
        final_chunks, final_metas = [x["text"] for x in scored_chunks[:3]], [x["meta"] for x in scored_chunks[:3]]

        yield json.dumps({"type": "meta", "sources": final_chunks, "debug": "Layer 3: Re-Ranked"}) + "\n"

        full_response = ""
        try:
            stream = llm_service.stream_answer(search_query, final_chunks, final_metas, detected_lang, history)
            for token in stream:
                full_response += token
                yield json.dumps({"type": "token", "content": token}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": "Generation failed."}) + "\n"; print(f"Stream Error: {e}"); return

        # Post-Processing & Saving
        elapsed = time.time() - start_time
        error_phrases = ["I apologize", "Error generating"]
        if not any(x in full_response for x in error_phrases):
            cache_service.set_qa_cache(product_context, detected_lang, search_query, full_response, final_chunks)
            vector_service.cache_answer(search_query, full_response, final_chunks, query_emb)
            cache_service.add_to_history(session_id, "user", body.question)
            cache_service.add_to_history(session_id, "assistant", full_response)
            
        _log_audit(db, search_query, full_response, detected_lang, elapsed, False, "Layer 3: Streamed & Re-Ranked")

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")