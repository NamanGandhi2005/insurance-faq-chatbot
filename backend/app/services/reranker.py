from sentence_transformers import CrossEncoder
import torch

class RerankerService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RerankerService, cls).__new__(cls)
            # This model is tiny (20MB) and very fast on CPU
            cls._model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')
        return cls._instance

    def rank_documents(self, query: str, documents: list[str], top_k: int = 3):
        if not documents: return []
        
        # Prepare pairs: [[query, doc1], [query, doc2]...]
        pairs = [[query, doc] for doc in documents]
        
        # Score them
        scores = self._model.predict(pairs)
        
        # Combine docs with scores and sort
        scored_docs = sorted(
            zip(documents, scores), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Return top K documents
        return [doc for doc, score in scored_docs[:top_k]]