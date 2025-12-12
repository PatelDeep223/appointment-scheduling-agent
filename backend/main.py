"""
Medical Appointment Scheduling Agent - Main Application
FastAPI backend with Calendly integration and RAG-based FAQ system
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uvicorn

# Import custom modules
from agent.scheduling_agent import SchedulingAgent
from rag.faq_rag import FAQRetriever
from api.calendly_integration import CalendlyClient
from models.schemas import (
    ChatMessage, ChatRequest, ChatResponse,
    AppointmentRequest, AppointmentResponse
)

# Initialize FastAPI app
app = FastAPI(
    title="Medical Appointment Scheduling Agent",
    description="AI-powered conversational agent for medical appointment scheduling",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
scheduling_agent = SchedulingAgent()
faq_retriever = FAQRetriever()
calendly_client = CalendlyClient()

# Session storage (in production, use Redis or database)
sessions: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Starting Medical Appointment Scheduling Agent...")
    print("📚 Loading FAQ knowledge base...")
    await faq_retriever.initialize()
    print("✅ System ready!")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Medical Appointment Scheduling Agent",
        "version": "1.0.0"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint for conversational interaction
    
    Args:
        request: ChatRequest containing user message and session_id
    
    Returns:
        ChatResponse with agent's reply and updated context
    """
    try:
        session_id = request.session_id
        user_message = request.message
        
        # Initialize or retrieve session
        if session_id not in sessions:
            sessions[session_id] = {
                "context": "greeting",
                "appointment_type": None,
                "patient_info": {},
                "conversation_history": []
            }
        
        session = sessions[session_id]
        
        # Add user message to history
        session["conversation_history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Process message through agent
        response = await scheduling_agent.process_message(
            message=user_message,
            session=session,
            faq_retriever=faq_retriever,
            calendly_client=calendly_client
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
        
        return ChatResponse(
            message=response["message"],
            context=session["context"],
            suggestions=response.get("suggestions", []),
            appointment_details=response.get("appointment_details")
        )
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/availability")
async def get_availability(
    date: str,
    appointment_type: str = "consultation"
):
    """
    Get available time slots for a specific date
    
    Args:
        date: Date in YYYY-MM-DD format
        appointment_type: Type of appointment
    
    Returns:
        List of available time slots
    """
    try:
        availability = await calendly_client.get_availability(
            date=date,
            appointment_type=appointment_type
        )
        return availability
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/book", response_model=AppointmentResponse)
async def book_appointment(request: AppointmentRequest):
    """
    Book an appointment
    
    Args:
        request: AppointmentRequest with booking details
    
    Returns:
        AppointmentResponse with confirmation details
    """
    try:
        booking = await calendly_client.create_booking(
            appointment_type=request.appointment_type,
            date=request.date,
            start_time=request.start_time,
            patient_name=request.patient_name,
            patient_email=request.patient_email,
            patient_phone=request.patient_phone,
            reason=request.reason
        )
        return booking
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/appointments/{booking_id}")
async def cancel_appointment(booking_id: str):
    """Cancel an appointment"""
    try:
        result = await calendly_client.cancel_booking(booking_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/faq/search")
async def search_faq(query: str):
    """
    Search FAQ knowledge base
    
    Args:
        query: Search query
    
    Returns:
        Relevant FAQ answers
    """
    try:
        results = await faq_retriever.search(query, top_k=3)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )