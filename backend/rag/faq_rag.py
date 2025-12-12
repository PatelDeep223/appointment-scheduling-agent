"""
FAQ RAG (Retrieval-Augmented Generation) System
Handles FAQ retrieval and answering using vector search
"""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from .vector_store import VectorStore
from .embeddings import get_embedding


class FAQRetriever:
    """
    FAQ retrieval system using RAG
    """
    
    def __init__(self):
        self.vector_store: Optional[VectorStore] = None
        self.clinic_data: Dict[str, Any] = {}
        self.initialized = False
    
    async def initialize(self):
        """
        Initialize the FAQ system by loading clinic data and building vector store
        """
        if self.initialized:
            return
        
        # Load clinic info
        data_path = Path(__file__).parent.parent.parent / "data" / "clinic_info.json"
        
        if not data_path.exists():
            raise FileNotFoundError(f"Clinic info file not found: {data_path}")
        
        with open(data_path, 'r') as f:
            self.clinic_data = json.load(f)
        
        # Initialize vector store
        vector_db_path = os.getenv("VECTOR_DB_PATH", "./data/vectordb")
        self.vector_store = VectorStore(persist_directory=vector_db_path)
        
        # Build knowledge base if empty
        if self.vector_store.get_collection_size() == 0:
            await self._build_knowledge_base()
        
        self.initialized = True
        print("✅ FAQ RAG system initialized")
    
    async def _build_knowledge_base(self):
        """Build the vector knowledge base from clinic_info.json"""
        documents = []
        metadatas = []
        ids = []
        
        doc_id = 0
        
        # Clinic Details
        clinic_details = self.clinic_data.get("clinic_details", {})
        
        # Location and directions
        if "address" in clinic_details:
            documents.append(
                f"Location: {clinic_details['name']} is located at {clinic_details['address']}. "
                f"Directions: {clinic_details.get('directions', '')}"
            )
            metadatas.append({"category": "location", "type": "address"})
            ids.append(f"location_{doc_id}")
            doc_id += 1
        
        # Parking information
        if "parking" in clinic_details:
            documents.append(f"Parking information: {clinic_details['parking']}")
            metadatas.append({"category": "location", "type": "parking"})
            ids.append(f"parking_{doc_id}")
            doc_id += 1
        
        # Hours of operation
        if "hours" in clinic_details:
            hours_text = "Hours of operation: "
            for day, time in clinic_details["hours"].items():
                hours_text += f"{day.replace('_', ' ').title()}: {time}. "
            documents.append(hours_text.strip())
            metadatas.append({"category": "hours", "type": "schedule"})
            ids.append(f"hours_{doc_id}")
            doc_id += 1
        
        # Insurance & Billing
        insurance_billing = self.clinic_data.get("insurance_billing", {})
        
        # Accepted insurance
        if "accepted_insurance" in insurance_billing:
            insurance_list = ", ".join(insurance_billing["accepted_insurance"])
            documents.append(
                f"We accept the following insurance providers: {insurance_list}. "
                f"Billing policy: {insurance_billing.get('billing_policy', '')}"
            )
            metadatas.append({"category": "insurance", "type": "providers"})
            ids.append(f"insurance_{doc_id}")
            doc_id += 1
        
        # Payment methods
        if "payment_methods" in insurance_billing:
            payment_list = ", ".join(insurance_billing["payment_methods"])
            documents.append(f"Payment methods accepted: {payment_list}")
            metadatas.append({"category": "billing", "type": "payment"})
            ids.append(f"billing_{doc_id}")
            doc_id += 1
        
        # Visit Preparation
        visit_prep = self.clinic_data.get("visit_preparation", {})
        
        # First visit documents
        if "first_visit_documents" in visit_prep:
            docs_list = ". ".join(visit_prep["first_visit_documents"])
            documents.append(
                f"For your first visit, please bring: {docs_list}. "
                f"Preparation tips: {visit_prep.get('preparation_tips', '')}"
            )
            metadatas.append({"category": "preparation", "type": "first_visit"})
            ids.append(f"first_visit_{doc_id}")
            doc_id += 1
        
        # What to bring
        if "what_to_bring" in visit_prep:
            bring_list = ", ".join(visit_prep["what_to_bring"])
            documents.append(f"Items to bring to your appointment: {bring_list}")
            metadatas.append({"category": "preparation", "type": "items"})
            ids.append(f"preparation_{doc_id}")
            doc_id += 1
        
        # Policies
        policies = self.clinic_data.get("policies", {})
        
        # Cancellation policy
        if "cancellation_policy" in policies:
            documents.append(f"Cancellation policy: {policies['cancellation_policy']}")
            metadatas.append({"category": "policies", "type": "cancellation"})
            ids.append(f"cancellation_{doc_id}")
            doc_id += 1
        
        # Late arrival policy
        if "late_arrival_policy" in policies:
            documents.append(f"Late arrival policy: {policies['late_arrival_policy']}")
            metadatas.append({"category": "policies", "type": "late_arrival"})
            ids.append(f"late_arrival_{doc_id}")
            doc_id += 1
        
        # COVID protocols
        if "covid_protocols" in policies:
            documents.append(f"COVID-19 protocols: {policies['covid_protocols']}")
            metadatas.append({"category": "policies", "type": "covid"})
            ids.append(f"covid_{doc_id}")
            doc_id += 1
        
        # Appointment types
        appt_types = self.clinic_data.get("appointment_types", {})
        for appt_key, appt_info in appt_types.items():
            appt_name = appt_key.replace("_", " ").title()
            documents.append(
                f"{appt_name}: {appt_info.get('description', '')} "
                f"Duration: {appt_info.get('duration', '')}. "
                f"Cost estimate: {appt_info.get('cost_estimate', '')}"
            )
            metadatas.append({"category": "appointment_types", "type": appt_key})
            ids.append(f"appt_type_{doc_id}")
            doc_id += 1
        
        # Common questions
        common_questions = self.clinic_data.get("common_questions", [])
        for qa in common_questions:
            documents.append(f"Question: {qa.get('question', '')} Answer: {qa.get('answer', '')}")
            metadatas.append({"category": "faq", "type": "common_question"})
            ids.append(f"faq_{doc_id}")
            doc_id += 1
        
        # Contact information
        if "phone" in clinic_details:
            documents.append(
                f"Contact information: Phone: {clinic_details['phone']}, "
                f"Email: {clinic_details.get('email', '')}"
            )
            metadatas.append({"category": "contact", "type": "info"})
            ids.append(f"contact_{doc_id}")
            doc_id += 1
        
        # Add all documents to vector store
        if documents:
            self.vector_store.add_documents(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"✅ Built knowledge base with {len(documents)} documents")
    
    async def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search FAQ knowledge base
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of relevant FAQ results
        """
        if not self.initialized:
            await self.initialize()
        
        results = self.vector_store.search(query, n_results=top_k)
        return results
    
    async def get_answer(self, category: str) -> str:
        """
        Get FAQ answer for a specific category
        
        Args:
            category: FAQ category (insurance, location, hours, parking, etc.)
            
        Returns:
            Formatted answer string
        """
        if not self.initialized:
            await self.initialize()
        
        # Map category to search query
        category_queries = {
            "insurance": "insurance providers accepted coverage",
            "location": "clinic address location where",
            "hours": "business hours open closed schedule",
            "parking": "parking garage validation",
            "cancellation": "cancel cancellation policy reschedule",
            "first_visit": "first visit new patient documents bring",
            "contact": "phone email contact reach",
            "payment": "payment methods billing cost price"
        }
        
        query = category_queries.get(category, category)
        results = await self.search(query, top_k=2)
        
        if not results:
            return f"I don't have specific information about {category}. Please call our office at +1-555-123-4567 for assistance."
        
        # Format answer
        answer_parts = []
        for result in results:
            answer_parts.append(result["document"])
        
        answer = " ".join(answer_parts)
        
        # Add clinic name if not present
        clinic_name = self.clinic_data.get("clinic_details", {}).get("name", "HealthCare Plus Clinic")
        if clinic_name not in answer:
            answer = f"{clinic_name}: {answer}"
        
        return answer
    
    async def get_contextual_answer(self, query: str, context: Optional[str] = None) -> str:
        """
        Get contextual answer for a query
        
        Args:
            query: User's question
            context: Optional conversation context
            
        Returns:
            Formatted answer
        """
        if not self.initialized:
            await self.initialize()
        
        # Enhance query with context if provided
        search_query = f"{context} {query}" if context else query
        
        results = await self.search(search_query, top_k=3)
        
        if not results:
            return "I don't have that information readily available. Please call our office at +1-555-123-4567 for assistance."
        
        # Format answer from top results
        answer = results[0]["document"]
        
        # If multiple relevant results, combine them
        if len(results) > 1 and results[1]["distance"] and results[1]["distance"] < 0.8:
            additional_info = results[1]["document"]
            answer = f"{answer} Additionally, {additional_info}"
        
        return answer
