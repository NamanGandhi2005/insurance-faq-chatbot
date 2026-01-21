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
            "You are an an AI data analyst for an insurance company. Your task is to answer the user's <question> by extracting structured data from the provided <documents>. "
            "Output your answer directly without any preamble or conversational filler. "
            "Follow these rules strictly:\n"
            "- Extract ONLY facts, numbers, and lists from the provided <documents>."
            "- Prioritize information from tables if available."
            "- If you cannot find the exact information in the documents, you MUST state: 'The provided documents do not contain specific details on this topic.'"
            "- Never ask the user for clarification."
            "- Do not mention the document source in your answer."
            "- Do not define terms like 'Sum Insured' unless specifically asked for a definition found in the documents. Only state the specific values."
            f"Provide the answer in {language}."
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
            
            buffer = ""
            is_answering = False

            for chunk in stream:
                content = chunk.choices[0].delta.content
                if not content:
                    continue
                
                buffer += content

                if not is_answering:
                    if "</think>" in buffer:
                        parts = buffer.split("</think>", 1)
                        answer_start = parts[1]
                        is_answering = True
                        if answer_start:
                            yield answer_start
                        buffer = ""
                else:
                    yield content
            
            if not is_answering and buffer:
                yield buffer

        except Exception as e:
            print(f"LLM Stream Error: {e}")
            yield "I apologize, but I encountered an error generating the response."