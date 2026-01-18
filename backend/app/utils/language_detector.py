# app/utils/language_detector.py
from langdetect import detect, LangDetectException

def detect_language(text: str) -> str:
    text_lower = text.lower()
    
    # 1. Hinglish Check
    hinglish_markers = [" hai", " kaise", " milega", " kya", " kab", " nahi", " haan", " lekin", " aur", " isme"]
    if any(marker in text_lower for marker in hinglish_markers):
        return "en" # Treat Hinglish as English for the LLM (it works better)

    # 2. Standard Detection with Whitelist
    try:
        lang = detect(text)
        # Only allow major languages supported by Qwen well
        allowed_langs = ['en', 'hi', 'fr', 'es', 'de']
        
        if lang in allowed_langs:
            return lang
        return "en" # Fallback to English for 'et', 'sv', etc.
    except LangDetectException:
        return "en"