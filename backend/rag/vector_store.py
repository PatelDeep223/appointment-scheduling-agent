"""
Vector store implementation using ChromaDB
Stores and retrieves FAQ embeddings for semantic search
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings

from .embeddings import get_embedding


class VectorStore:
    """
    Vector store for FAQ knowledge base using ChromaDB
    """
    
    def __init__(self, persist_directory: str = "./data/vectordb"):
        """
        Initialize vector store
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="clinic_faq",
            metadata={"description": "FAQ knowledge base for clinic"}
        )
        
        print(f"✅ Vector store initialized at {self.persist_directory}")
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ):
        """
        Add documents to the vector store
        
        Args:
            documents: List of document texts
            metadatas: List of metadata dictionaries
            ids: List of unique document IDs
        """
        # Generate embeddings
        embeddings = [get_embedding(doc) for doc in documents]
        
        # Add to collection
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"✅ Added {len(documents)} documents to vector store")
    
    def search(
        self,
        query: str,
        n_results: int = 3,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents
        
        Args:
            query: Search query text
            n_results: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of search results with document, metadata, and distance
        """
        # Generate query embedding
        query_embedding = get_embedding(query)
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None,
                    "id": results['ids'][0][i]
                })
        
        return formatted_results
    
    def clear_collection(self):
        """Clear all documents from the collection"""
        self.client.delete_collection(name="clinic_faq")
        self.collection = self.client.create_collection(
            name="clinic_faq",
            metadata={"description": "FAQ knowledge base for clinic"}
        )
        print("🗑️ Vector store cleared")
    
    def get_collection_size(self) -> int:
        """Get number of documents in collection"""
        return self.collection.count()

