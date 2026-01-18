# backend/scripts/seed_faq.py
import sys
import os

# Path Setup
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.dirname(script_dir)
sys.path.append(backend_path)

# --- IMPORTS FOR SEMANTIC CACHING ---
from app.services.embedding_service import EmbeddingService
from app.services.vector_db import VectorDBService

# 1. Define the "Golden" Q&A pairs
faq_data = [
    {
        "question": "What is the waiting period?",
        "answer": "**Waiting Periods:**\n1. **Initial Waiting Period:** 30 days (except accidents).\n2. **Specific Diseases:** 24 months (e.g., Cataract, Hernia).\n3. **Pre-Existing Diseases (PED):** 36 months (can be reduced to 2 years with add-on).\n4. **Technology Wait Period:** Reduced from 3 to 2 years.",
        "sources": ["Admin Verified Source (Policy Sec 4.1)"]
    },
    {
        "question": "Does it cover Ayurveda or AYUSH treatment?",
        "answer": "Yes, **AYUSH treatment** (Ayurveda, Yoga, Unani, Siddha, and Homeopathy) is covered up to the Sum Insured, provided the treatment is taken at a government-recognized institute.",
        "sources": ["Policy Document - Benefits Section"]
    },
    {
        "question": "How do I file a cashless claim?",
        "answer": "**To file a Cashless Claim:**\n1. Visit a Network Hospital.\n2. Show your Health Card/Policy Copy at the TPA desk.\n3. Fill out the Pre-Authorization form.\n4. The hospital will send the request to us.\n5. Once approved, we settle the bill directly with the hospital.",
        "sources": ["Claims Process Guide"]
    },
    {
        "question": "What documents are required for reimbursement?",
        "answer": "**Required Documents:**\n- Duly filled Claim Form.\n- Original Discharge Summary.\n- Original Hospital Bills & Receipts.\n- Pharmacy/Chemist Bills with prescriptions.\n- Investigation Reports (X-Ray, MRI, Labs).\n- KYC Documents (Aadhaar/PAN).",
        "sources": ["Claims Checklist"]
    },
    {
        "question": "Is there a limit on Room Rent?",
        "answer": "**No Sub-limit.** You are eligible for a **Single Private Room** or up to the Sum Insured. There is no capping on ICU charges either.",
        "sources": ["Product Highlights - Page 1"]
    },
    {
        "question": "What is covered under Pre and Post Hospitalization?",
        "answer": "The policy covers:\n- **Pre-Hospitalization:** Medical expenses incurred **30 days** before admission.\n- **Post-Hospitalization:** Medical expenses incurred **60 days** after discharge.",
        "sources": ["Policy Schedule - Section B"]
    },
    {
        "question": "What is not covered? (Exclusions)",
        "answer": "**Common Exclusions:**\n- Expenses for cosmetic or plastic surgery.\n- Breach of law/criminal intent.\n- Alcohol or drug abuse related treatments.\n- Self-inflicted injuries (Suicide attempts).\n- War or nuclear activity related injuries.",
        "sources": ["Policy Exclusions - Annexure I"]
    },
    {
        "question": "Is maternity covered?",
        "answer": "Maternity coverage depends on your specific plan variant. In the standard base plan, maternity is usually **excluded** or has a 9-month to 24-month waiting period if the 'Maternity Add-on' was purchased.",
        "sources": ["Product Variations Guide"]
    },
    {
        "question": "What is the Free Look Period?",
        "answer": "You have a **Free Look Period of 15 days** from the date of receipt of the policy document. If you are not satisfied with the terms, you can cancel the policy and get a refund of the premium (subject to deduction for stamp duty and pro-rata risk cover).",
        "sources": ["Terms & Conditions - Page 12"]
    },
    {
        "question": "Does this policy cover COVID-19?",
        "answer": "Yes, **COVID-19** is treated as any other viral infection. Hospitalization expenses arising from COVID-19 are covered up to the Sum Insured, subject to the initial 30-day waiting period.",
        "sources": ["Circular 2021 - Pandemic Coverage"]
    }
]

def seed_semantic_cache():
    print("--- Seeding Semantic Cache (ChromaDB) ---")
    print("Loading embedding model (this may take a few seconds)...")
    
    # Initialize Services
    embed_service = EmbeddingService()
    vector_service = VectorDBService()

    count = 0
    for item in faq_data:
        print(f"Processing: {item['question']}")
        
        # 1. Generate Embedding
        # We need the vector so the chatbot can find this even if worded differently
        emb = embed_service.generate_embedding(item["question"])
        
        # 2. Store in Vector DB (Semantic Cache Collection)
        vector_service.cache_answer(
            question=item["question"],
            answer=item["answer"],
            sources=item["sources"],
            embedding=emb
        )
        count += 1

    print(f"--- Success! Seeded {count} answers into Semantic Cache ---")

if __name__ == "__main__":
    seed_semantic_cache()