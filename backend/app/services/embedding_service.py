# app/services/embedding_service.py
from sentence_transformers import SentenceTransformer
from app.config import settings

class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            # Load model (downloads on first run)
            print(f"Loading embedding model: {settings.EMBEDDING_MODEL}...")
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            print("Model loaded successfully.")
        return cls._instance

    def generate_embedding(self, text: str):
        # multilingual-e5 requires "query: " prefix for questions and "passage: " for documents
        # For general embedding, we will just use the text, but for better performance
        # you might want to prepend "passage: " here if strictly for storage.
        # We will keep it raw for now and handle prefixes in the calling logic.
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def generate_batch_embeddings(self, texts: list[str]):
        return self._model.encode(texts, normalize_embeddings=True).tolist()