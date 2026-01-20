# app/services/llm_service.py
import time
import httpx
from openai import OpenAI
from app.config import settings


class LLMService:
    def __init__(self):
        # Use OpenAI client with Groq's OpenAI-compatible endpoint
        self.client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=httpx.Timeout(60.0, connect=10.0),
            http_client=httpx.Client(
                timeout=httpx.Timeout(60.0, connect=10.0),
                follow_redirects=True
            )
        )
        self.model = settings.GROQ_MODEL
        self.max_retries = 3

    def _call_with_retry(self, messages: list, max_tokens: int, temperature: float) -> str:
        """Helper method to call API with retry logic."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                print(f"LLM API attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1.5)  # Wait before retry

        raise last_error

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
            result = self._call_with_retry(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.3
            )
            return result.strip()
        except Exception as e:
            print(f"Contextualize error after retries: {e}")
            return current_question

    def generate_answer(
        self,
        question: str,
        context_chunks: list[str],
        metadatas: list[dict],
        language: str = "en",
        history: list = []
    ) -> str:

        # 1. Format PDF Context
        formatted_context = []
        for i, chunk in enumerate(context_chunks):
            product = metadatas[i].get("product_name", "Unknown Policy")
            formatted_context.append(f"--- SOURCE: {product} ---\n{chunk}")
        context_text = "\n\n".join(formatted_context)

        # 2. Format Chat History (Last 4 messages)
        history_text = ""
        if history:
            recent_msgs = history[-4:]
            conversation_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent_msgs])
            history_text = f"PREVIOUS CONVERSATION:\n{conversation_str}\n"

        # 3. Language/Style Instruction - Always respond in English unless specified
        if language and language != "en":
            lang_instruction = f"Answer in {language}."
        else:
            lang_instruction = "Always respond in English only. Do not use Hinglish or any other language."

        # 4. System Prompt
        system_prompt = (
            "You are a professional insurance assistant. "
            f"{lang_instruction} "
            "Use the PREVIOUS CONVERSATION and DOCUMENT CONTEXT to answer. "
            "If the user asks about details they mentioned earlier (like claim amounts), use the Conversation History. "
            "If the user asks about policy rules, use the Document Context. "
            "Be professional and concise in your responses."
        )

        # 5. Final Prompt Structure
        user_prompt = f"""
{history_text}

DOCUMENT CONTEXT:
{context_text}

CURRENT QUESTION: {question}
"""

        try:
            result = self._call_with_retry(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=500,
                temperature=0.7
            )
            return result
        except Exception as e:
            print(f"LLM Error after retries: {e}")
            return "I apologize, but I encountered an error. Please try again."
