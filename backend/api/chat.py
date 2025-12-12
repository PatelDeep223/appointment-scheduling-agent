"""
Chat API endpoint handlers
Additional chat-related endpoints and utilities
"""

from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from datetime import datetime

from models.schemas import ChatRequest, ChatResponse
from agent.scheduling_agent import SchedulingAgent
from rag.faq_rag import FAQRetriever
from api.calendly_integration import CalendlyClient


class ChatHandler:
    """
    Handler for chat-related operations
    """
    
    def __init__(
        self,
        scheduling_agent: SchedulingAgent,
        faq_retriever: FAQRetriever,
        calendly_client: CalendlyClient
    ):
        self.scheduling_agent = scheduling_agent
        self.faq_retriever = faq_retriever
        self.calendly_client = calendly_client
    
    async def process_chat(
        self,
        request: ChatRequest,
        sessions: Dict[str, Dict[str, Any]]
    ) -> ChatResponse:
        """
        Process a chat message and return response
        
        Args:
            request: Chat request with message and session_id
            sessions: Session storage dictionary
            
        Returns:
            Chat response with agent's reply
        """
        session_id = request.session_id
        user_message = request.message
        
        # Initialize or retrieve session
        if session_id not in sessions:
            sessions[session_id] = {
                "context": "greeting",
                "appointment_type": None,
                "patient_info": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat()
            }
        
        session = sessions[session_id]
        
        # Add user message to history
        session["conversation_history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Process message through agent
            response = await self.scheduling_agent.process_message(
                message=user_message,
                session=session,
                faq_retriever=self.faq_retriever,
                calendly_client=self.calendly_client
            )
            
            # Add agent response to history
            session["conversation_history"].append({
                "role": "assistant",
                "content": response["message"],
                "timestamp": datetime.now().isoformat()
            })
            
            # Update session
            session["context"] = response.get("context", session["context"])
            if "appointment_type" in response:
                session["appointment_type"] = response["appointment_type"]
            if "selected_slot" in response:
                session["selected_slot"] = response["selected_slot"]
            if "patient_info" in response:
                session["patient_info"] = {**session.get("patient_info", {}), **response["patient_info"]}
            
            return ChatResponse(
                message=response["message"],
                context=session["context"],
                suggestions=response.get("suggestions", []),
                appointment_details=response.get("appointment_details")
            )
            
        except Exception as e:
            print(f"❌ Error processing chat: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")
    
    async def get_session_history(
        self,
        session_id: str,
        sessions: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session
        
        Args:
            session_id: Session identifier
            sessions: Session storage dictionary
            
        Returns:
            List of conversation messages
        """
        if session_id not in sessions:
            return []
        
        return sessions[session_id].get("conversation_history", [])
    
    async def reset_session(
        self,
        session_id: str,
        sessions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Reset a session (clear conversation history)
        
        Args:
            session_id: Session identifier
            sessions: Session storage dictionary
            
        Returns:
            Reset confirmation
        """
        sessions[session_id] = {
            "context": "greeting",
            "appointment_type": None,
            "patient_info": {},
            "conversation_history": [],
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "message": "Session reset successfully"
        }

