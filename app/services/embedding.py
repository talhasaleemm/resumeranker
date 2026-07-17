"""
app/services/embedding.py — Dense Vector Embedding generation service.
"""
import logging
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        logger.info("Initializing EmbeddingService (loading all-MiniLM-L6-v2)...")
        # Load the pre-downloaded local cached model
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("EmbeddingService initialized successfully.")

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate a 384-dimensional vector embedding for the input text.
        """
        if not text or not text.strip():
            # Return a zero vector if input is empty
            return [0.0] * 384
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

def get_embedding_service() -> EmbeddingService:
    return EmbeddingService.get_instance()
