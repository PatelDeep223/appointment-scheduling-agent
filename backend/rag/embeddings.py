"""
Embedding utilities for RAG system
Handles text embedding generation using OpenAI or sentence-transformers
"""

import os
from typing import List
import numpy as np

# Try OpenAI first, fallback to sentence-transformers
try:
    from openai import OpenAI
    USE_OPENAI = True
    client = None
except ImportError:
    USE_OPENAI = False

if not USE_OPENAI:
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        USE_SENTENCE_TRANSFORMERS = True
    except ImportError:
        USE_SENTENCE_TRANSFORMERS = False
        model = None
else:
    USE_SENTENCE_TRANSFORMERS = False


def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text
    
    Args:
        text: Input text to embed
        
    Returns:
        List of float values representing the embedding
    """
    global client
    
    if USE_OPENAI:
        if client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            client = OpenAI(api_key=api_key)
        
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"OpenAI embedding error, falling back to sentence-transformers: {e}")
            # Fallback to sentence-transformers
            if not USE_SENTENCE_TRANSFORMERS:
                raise
            return model.encode(text).tolist()
    
    elif USE_SENTENCE_TRANSFORMERS:
        if model is None:
            raise ValueError("Sentence transformer model not loaded")
        return model.encode(text).tolist()
    
    else:
        raise ValueError("No embedding model available. Install openai or sentence-transformers")


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (batch processing)
    
    Args:
        texts: List of input texts to embed
        
    Returns:
        List of embeddings (each is a list of floats)
    """
    if USE_OPENAI:
        global client
        if client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            client = OpenAI(api_key=api_key)
        
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"OpenAI batch embedding error, falling back to sentence-transformers: {e}")
            if not USE_SENTENCE_TRANSFORMERS:
                raise
            return model.encode(texts).tolist()
    
    elif USE_SENTENCE_TRANSFORMERS:
        if model is None:
            raise ValueError("Sentence transformer model not loaded")
        return model.encode(texts).tolist()
    
    else:
        raise ValueError("No embedding model available")

