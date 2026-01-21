from sentence_transformers import SentenceTransformer
from app.config import settings

class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            print(f"Loading embedding model: {settings.EMBEDDING_MODEL}...")
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            print("Model loaded successfully.")
        return cls._instance

    def generate_document_embedding(self, text: str):
        """Prepends 'passage: ' for E5 models."""
        return self._model.encode(f"passage: {text}", normalize_embeddings=True).tolist()

    def generate_query_embedding(self, query: str):
        """Prepends 'query: ' for E5 models."""
        return self._model.encode(f"query: {query}", normalize_embeddings=True).tolist()

    def generate_batch_document_embeddings(self, texts: list[str]):
        processed_texts = [f"passage: {t}" for t in texts]
        return self._model.encode(processed_texts, normalize_embeddings=True).tolist()
