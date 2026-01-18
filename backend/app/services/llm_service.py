# app/services/llm_service.py
import ollama
from app.config import settings

class LLMService:
    def __init__(self):
        self.model = settings.OLLAMA_MODEL

    def contextualize_query(self, history: list, current_question: str) -> str:
        """
        Rewrites user question based on history for better search.
        """
        if not history:
            return current_question

        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]])
        
        prompt = (
            "Given the conversation history, rewrite the last user input to be a standalone question. "
            "Do not answer it. Just clarify what the user is asking.\n\n"
            f"History:\n{history_text}\n\n"
            f"User Input: {current_question}\n\n"
            "Rewritten Question:"
        )

        try:
            response = ollama.generate(
                model=self.model, 
                prompt=prompt,
                options={"num_ctx": 1024, "num_predict": 40},
                keep_alive="1h"
            )
            return response['response'].strip()
        except:
            return current_question

    def generate_answer(
        self, 
        question: str, 
        context_chunks: list[str], 
        metadatas: list[dict], 
        language: str = "en",
        history: list = []  # <--- NEW PARAMETER
    ) -> str:
        
        # 1. Format PDF Context
        formatted_context = []
        for i, chunk in enumerate(context_chunks):
            product = metadatas[i].get("product_name", "Unknown Policy")
            formatted_context.append(f"--- SOURCE: {product} ---\n{chunk}")
        context_text = "\n\n".join(formatted_context)
        
        # 2. Format Chat History (Last 4 messages)
        # This allows the AI to "remember" what was said previously
        history_text = ""
        if history:
            recent_msgs = history[-4:] # Keep it short to save VRAM
            conversation_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent_msgs])
            history_text = f"PREVIOUS CONVERSATION:\n{conversation_str}\n"

        # 3. Language/Style Instruction
        lang_instruction = f"Answer in {language}."
        if language == "en":
            lang_instruction = (
                "Answer in the same language/style as the user (English or Hinglish). "
            )

        # 4. System Prompt
        system_prompt = (
            "You are an expert insurance assistant. "
            "Use the provided DOCUMENT CONTEXT to answer the question. "
            "RULES:"
            "1. If the document contains specific numbers, lists, or currency amounts (e.g., 25L, 50L), YOU MUST LIST THEM."
            "2. Do NOT provide generic definitions or hypothetical examples (like 'say 5 lakhs') unless the user asks for an explanation."
            "3. If the text looks like a table row (e.g., 'Sum Insured 25L/50L'), extract those values accurately."
            f" {lang_instruction}"
        )
        
        # 5. Final Prompt Structure
        user_prompt = f"""
        {history_text}
        
        DOCUMENT CONTEXT:
        {context_text}
        
        CURRENT QUESTION: {question}
        """

        try:
            response = ollama.chat(
                model=self.model, 
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                options={
                    "num_ctx": 3072,    # Increased context window to fit history
                    "num_predict": 300, 
                    "temperature": 0.7, 
                    "num_thread": 8
                },
                keep_alive="1h"
            )
            return response['message']['content']
        except Exception as e:
            print(f"LLM Error: {e}")
            return "I apologize, but I encountered an error."
        
    def stream_answer(
        self, 
        question: str, 
        context_chunks: list[str], 
        metadatas: list[dict], 
        language: str = "en",
        history: list = []
    ):
        """
        Generator function that yields text tokens as they are generated.
        """
        # 1. Format Context
        formatted_context = []
        for i, chunk in enumerate(context_chunks):
            product = metadatas[i].get("product_name", "Unknown Policy")
            formatted_context.append(f"--- SOURCE: {product} ---\n{chunk}")
        context_text = "\n\n".join(formatted_context)

        # 2. Format History
        history_text = ""
        if history:
            recent_msgs = history[-4:]
            conversation_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent_msgs])
            history_text = f"PREVIOUS CONVERSATION:\n{conversation_str}\n"

        # 3. Prompt Construction
        lang_instruction = f"Answer in {language}."
        if language == "en":
            lang_instruction = "Answer in the same language/style as the user (English or Hinglish)."

        system_prompt = (
            "You are an insurance assistant. Use the PREVIOUS CONVERSATION and DOCUMENT CONTEXT to answer. "
            f"{lang_instruction}"
        )
        
        user_prompt = f"""
        {history_text}
        DOCUMENT CONTEXT:
        {context_text}
        CURRENT QUESTION: {question}
        """

        # 4. STREAMING CALL TO OLLAMA
        stream = ollama.chat(
            model=self.model, 
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            options={
                "num_ctx": 3072,
                "num_predict": 300, 
                "temperature": 0.7, 
                "num_thread": 8
            },
            keep_alive="1h",
            stream=True  # <--- CRITICAL: ENABLE STREAMING
        )

        # Yield chunks
        for chunk in stream:
            content = chunk['message']['content']
            if content:
                yield content