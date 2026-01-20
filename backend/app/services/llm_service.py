import re
from groq import Groq
from app.config import settings

class LLMService:
    def __init__(self):
        self.model = settings.GROQ_MODEL
        self.client = Groq(api_key=settings.GROQ_API_KEY)

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
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                temperature=0,
                max_tokens=1024,
                top_p=1,
                stop=None,
            )
            rewritten = chat_completion.choices[0].message.content.strip()
            # Safety check: if LLM returns empty or hallucinated long text, use original
            if not rewritten or len(rewritten) > len(current_question) * 4:
                return current_question
            return rewritten
        except Exception as e:
            print(f"LLM contextualize_query Error: {e}")
            return current_question

    def _build_prompt(self, question, context_chunks, metadatas, language, history):
        # 1. Format and Clean PDF Context using XML tags for clarity
        formatted_context = []
        for i, chunk in enumerate(context_chunks):
            product = metadatas[i].get("product_name", "Unknown Policy")
            # Clean up whitespace to make tables more readable for the AI
            clean_chunk = re.sub(r'\s+', ' ', chunk).strip()
            formatted_context.append(f"<document source='{product}'>\n{clean_chunk}\n</document>")
        context_text = "\n\n".join(formatted_context)
        
        # 2. Format Chat History (remains the same)
        history_text = ""
        if history:
            recent_msgs = history[-4:]
            conversation_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent_msgs])
            history_text = f"<history>\n{conversation_str}\n</history>\n"

        # --- THE FINAL, SUPER-STRICT PROMPT ---
        system_prompt = (
            "You are an AI data analyst for an insurance company. Your task is to answer the user's <question> by extracting structured data from the provided <documents>. "
            "Follow this strict process:\n\n"
            "1. **Identify User Intent:** Analyze the <question> to understand the primary topic. Key topics include: 'Sum Insured', 'Eligibility', 'Waiting Period', 'Coverage', 'Bonus', 'Exclusions', or a specific benefit name.\n\n"
            "2. **Targeted Data Extraction:** Scan the <documents> for sections matching the user's intent. Your goal is to find and extract the following types of information above all else:\n"
            "   - **Currency Amounts & Limits:** (e.g., '₹5 Lakhs', 'Up to 1 Crore', '50L/100L', 'up to ₹10,000').\n"
            "   - **Time Periods:** (e.g., '30 days', '24 months', '3 years', '90 days').\n"
            "   - **Percentages:** (e.g., '10% co-payment', '50% of SI per year').\n"
            "   - **Lists of Benefits or Conditions:** (e.g., 'In-patient care, Day care treatment...').\n\n"
            "3. **Synthesize the Final Answer:** Construct a direct answer using ONLY the facts, numbers, and lists you extracted. Start with the most important data point (like the Sum Insured amount) first.\n\n"
            "**CRITICAL RULES:**\n"
            "- **PRIORITIZE TABLES:** If you see text that looks like a table (e.g., `Sum Insured - 5L/7L/10L`), prioritize extracting from it.\n"
            "- **NO GENERAL KNOWLEDGE:** Do not define what 'Sum Insured' is in general. Only state the specific Sum Insured values found in the documents.\n"
            "- **NO HALLUCINATION:** If you cannot find the exact information, you MUST state: 'The provided documents do not contain specific details on this topic.'\n"
            "- **NO QUESTIONS:** Never ask the user for clarification. Answer based only on what you are given.\n"
            "- **DO NOT MENTION SOURCES:** Do not mention the document source in your answer. The answer should be direct and straightforward."
        )
        
        user_prompt = f"""
        Here are the documents to use:
        <documents>
        {context_text}
        </documents>

        {history_text}

        <question>
        {question}
        </question>

        Based on your instructions, what is the answer in {language}?
        """
        return system_prompt, user_prompt

    def generate_answer(
        self, 
        question: str, 
        context_chunks: list[str], 
        metadatas: list[dict], 
        language: str = "en",
        history: list = []
    ) -> str:
        """Generates a complete, non-streaming answer."""
        system_prompt, user_prompt = self._build_prompt(question, context_chunks, metadatas, language, history)

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                model=self.model,
                temperature=0.5,
                max_tokens=300,
                top_p=1,
                stop=None,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"LLM Error: {e}")
            return "I apologize, but I encountered an error generating the response."

    def stream_answer(
        self, 
        question: str, 
        context_chunks: list[str], 
        metadatas: list[dict], 
        language: str = "en",
        history: list = []
    ):
        """Generates a streaming answer while suppressing <think> blocks in real-time."""
        system_prompt, user_prompt = self._build_prompt(question, context_chunks, metadatas, language, history)

        try:
            stream = self.client.chat.completions.create(
                model=self.model, 
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.5,
                max_tokens=300,
                top_p=1,
                stop=None,
                stream=True,
            )
            
            # Buffering logic to hide <think> tags
            buffer = ""
            is_answering = False

            for chunk in stream:
                content = chunk.choices[0].delta.content
                if not content:
                    continue
                
                # If we are already past the thinking phase, yield content immediately
                if is_answering:
                    yield content
                    continue
                
                # Otherwise, buffer the content
                buffer += content

                # Check if we have found the end of the thought block
                if "</think>" in buffer:
                    # Split the buffer: ignore part before tag, keep part after
                    parts = buffer.split("</think>")
                    answer_start = parts[-1]  # The part after </think>
                    
                    is_answering = True
                    if answer_start:
                        yield answer_start
                    buffer = "" # clear buffer
                
                # Fallback: If buffer gets long and no <think> tag was ever found at the start,
                # assume the model is answering directly without thoughts.
                elif len(buffer) > 20 and "<think>" not in buffer:
                    is_answering = True
                    yield buffer
                    buffer = ""

        except Exception as e:
            print(f"Stream Error: {e}")
            yield "I apologize, but I encountered an error."