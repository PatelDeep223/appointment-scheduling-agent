"""
Medical Appointment Scheduling Agent - Main Application
FastAPI backend with Calendly integration and RAG-based FAQ system
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uvicorn
import json

# Import custom modules
from agent.scheduling_agent import SchedulingAgent
from rag.faq_rag import FAQRetriever
from api.calendly_integration import CalendlyClient
from tools.availability_tool import AvailabilityTool
from models.schemas import (
    ChatMessage, ChatRequest, ChatResponse,
    AppointmentRequest, AppointmentResponse,
    BookingRequest, BookingResponse, PatientInfo
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

# Include booking routes
try:
    from api.bookings import router as bookings_router
    app.include_router(bookings_router)
    print("✅ Booking API routes included")
except ImportError:
    try:
        from .api.bookings import router as bookings_router
        app.include_router(bookings_router)
        print("✅ Booking API routes included")
    except ImportError:
        print("⚠️  Booking API routes not available")

# Initialize components
# Use LLM for natural conversational responses (set use_llm=False to disable)
scheduling_agent = SchedulingAgent(use_llm=True)
faq_retriever = FAQRetriever()
calendly_client = CalendlyClient()
availability_tool = AvailabilityTool(calendly_client)

# Session storage (in production, use Redis or database)
sessions: Dict[str, Dict[str, Any]] = {}

# Global flag to track if database is available
db_available = False


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Starting Medical Appointment Scheduling Agent...")
    
    # Initialize database and create tables
    global db_available
    db_available = False
    try:
        # Try direct import first (when running from backend/ directory)
        try:
            from database import init_db
        except ImportError:
            # Fallback to relative import
            try:
                from .database import init_db
            except ImportError:
                # Fallback to absolute import
                from backend.database import init_db
        
        db_available = init_db()
        if not db_available:
            print("   Continuing in demo mode (database not available)")
    except Exception as e:
        print(f"⚠️  Database initialization error: {e}")
        print("   Continuing in demo mode (using in-memory storage)")
        db_available = False
    
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
                "previous_context": None,
                "appointment_type": None,
                "patient_info": {},
                "available_slots": [],
                "selected_slot": None,
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
        
        # Update session - preserve previous context if switching
        if "previous_context" in response:
            session["previous_context"] = response["previous_context"]
        
        # Update context
        new_context = response.get("context", session["context"])
        if new_context != session["context"]:
            session["previous_context"] = session["context"]
        session["context"] = new_context
        
        # Update other session fields
        if "appointment_type" in response:
            session["appointment_type"] = response["appointment_type"]
        if "available_slots" in response:
            session["available_slots"] = response["available_slots"]
        if "selected_slot" in response:
            session["selected_slot"] = response["selected_slot"]
        if "patient_info" in response:
            session["patient_info"] = {**session.get("patient_info", {}), **response["patient_info"]}
        
        # Store system prompt info in session for reference
        if "current_system_prompt" in response:
            session["current_system_prompt"] = response.get("current_system_prompt")
        
        return ChatResponse(
            message=response["message"],
            context=session["context"],
            suggestions=response.get("suggestions", []),
            appointment_details=response.get("appointment_details"),
            available_slots=response.get("available_slots")  # Include structured slots for UI
        )
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/availability")
async def get_availability(
    date: str,
    appointment_type: str = "consultation",
    time_preference: Optional[str] = None
):
    """
    Get available time slots for a specific date
    
    Uses the AvailabilityTool for better error handling and filtering.
    
    Args:
        date: Date in YYYY-MM-DD format
        appointment_type: Type of appointment (can be key like "consultation" or display name)
        time_preference: Optional time preference filter ("morning", "afternoon", "evening")
    
    Returns:
        Dictionary with available slots:
        {
            "date": "YYYY-MM-DD",
            "appointment_type": "Appointment Type Name",
            "available_slots": [
                {
                    "start_time": "09:00 AM",
                    "end_time": "09:30 AM",
                    "available": True,
                    "raw_time": "09:00"
                },
                ...
            ],
            "message": "Optional message" (if no slots found)
        }
    """
    try:
        # Use availability_tool for better error handling and filtering
        availability = await availability_tool.get_available_slots(
            date=date,
            appointment_type=appointment_type,
            time_preference=time_preference
        )
        return availability
    except ValueError as e:
        # Client error (invalid input)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Server error
        print(f"❌ Error in /api/availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendly/availability")
async def get_calendly_availability(
    date: str,
    appointment_type: str = "consultation"
):
    """
    Mock Calendly API endpoint for availability checking
    
    This endpoint matches the mock Calendly API specification:
    - GET /api/calendly/availability
    - Query params: date (YYYY-MM-DD), appointment_type (consultation|followup|physical|specialist)
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2024-01-15")
        appointment_type: Type of appointment - "consultation" | "followup" | "physical" | "specialist" (or "special" which maps to "specialist")
    
    Returns:
        JSON response with available slots:
        {
            "date": "2024-01-15",
            "available_slots": [
                {"start_time": "09:00", "end_time": "09:30", "available": true},
                {"start_time": "09:30", "end_time": "10:00", "available": false},
                ...
            ]
        }
    """
    try:
        # Use the Calendly client to get availability
        availability = await calendly_client.get_availability(
            date=date,
            appointment_type=appointment_type
        )
        
        # Transform to match the mock API format from the image
        # Convert time format from "09:00 AM" to "09:00" (HH:MM)
        formatted_slots = []
        for slot in availability.get("available_slots", []):
            # Extract raw_time or parse from start_time
            raw_time = slot.get("raw_time")
            if not raw_time:
                # Try to parse from start_time (e.g., "09:00 AM" -> "09:00")
                start_time_str = slot.get("start_time", "")
                try:
                    dt = datetime.strptime(start_time_str, "%I:%M %p")
                    raw_time = dt.strftime("%H:%M")
                except:
                    raw_time = start_time_str
            
            # Calculate end_time in HH:MM format
            end_time_str = slot.get("end_time", "")
            end_time_raw = None
            if end_time_str:
                try:
                    dt = datetime.strptime(end_time_str, "%I:%M %p")
                    end_time_raw = dt.strftime("%H:%M")
                except:
                    # If parsing fails, try to calculate from start + duration
                    if raw_time:
                        start_hour, start_min = map(int, raw_time.split(":"))
                        duration = calendly_client.appointment_types.get(
                            calendly_client._normalize_appointment_type(appointment_type), {}
                        ).get("duration", 30)
                        end_min = start_min + duration
                        end_hour = start_hour + (end_min // 60)
                        end_min = end_min % 60
                        end_time_raw = f"{end_hour:02d}:{end_min:02d}"
            else:
                # Calculate from start time + duration
                if raw_time:
                    start_hour, start_min = map(int, raw_time.split(":"))
                    duration = calendly_client.appointment_types.get(
                        calendly_client._normalize_appointment_type(appointment_type), {}
                    ).get("duration", 30)
                    end_min = start_min + duration
                    end_hour = start_hour + (end_min // 60)
                    end_min = end_min % 60
                    end_time_raw = f"{end_hour:02d}:{end_min:02d}"
            
            formatted_slots.append({
                "start_time": raw_time or "09:00",
                "end_time": end_time_raw or "09:30",
                "available": slot.get("available", True)
            })
        
        return {
            "date": availability.get("date", date),
            "available_slots": formatted_slots
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error in /api/calendly/availability: {str(e)}")
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


@app.post("/api/calendly/book")
async def calendly_book(request: BookingRequest):
    """
    Mock Calendly API endpoint for booking appointments
    
    This endpoint matches the mock Calendly API specification:
    - POST /api/calendly/book
    - Body: JSON with appointment_type, date, start_time, patient (name, email, phone), reason
    
    Args:
        request: BookingRequest with booking details:
        {
            "appointment_type": "consultation",
            "date": "2024-01-15",
            "start_time": "10:00",
            "patient": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1-555-0100"
            },
            "reason": "Annual checkup"
        }
    
    Returns:
        JSON response with booking confirmation:
        {
            "booking_id": "APPT-2024-001",
            "status": "confirmed",
            "confirmation_code": "ABC123",
            "details": {...}
        }
    """
    try:
        # Create booking using Calendly client
        booking = await calendly_client.create_booking(
            appointment_type=request.appointment_type,
            date=request.date,
            start_time=request.start_time,
            patient_name=request.patient.name,
            patient_email=request.patient.email,
            patient_phone=request.patient.phone,
            reason=request.reason
        )
        
        # Transform to match the mock API format from the image
        return {
            "booking_id": booking.get("booking_id", ""),
            "status": booking.get("status", "confirmed"),
            "confirmation_code": booking.get("confirmation_code", ""),
            "details": {
                "appointment_type": booking.get("appointment_type", ""),
                "date": booking.get("date", ""),
                "start_time": booking.get("start_time", ""),
                "end_time": booking.get("end_time", ""),
                "duration": booking.get("duration", 30),
                "patient_name": booking.get("patient_name", ""),
                "patient_email": booking.get("patient_email", ""),
                "patient_phone": booking.get("patient_phone", ""),
                "reason": booking.get("reason", ""),
                "scheduling_link": booking.get("scheduling_link", ""),
                "clinic_info": booking.get("clinic_info", {}),
                "created_at": booking.get("created_at", "")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error in /api/calendly/book: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/appointments/{booking_id}")
async def cancel_appointment(booking_id: str):
    """Cancel an appointment"""
    try:
        result = await calendly_client.cancel_booking(booking_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calendly/webhook")
async def calendly_webhook(request: Request):
    """
    Calendly webhook endpoint to receive booking events
    
    Calendly sends webhook events for:
    - invitee.created: When a booking is confirmed
    - invitee.canceled: When a booking is canceled
    
    Configure this URL in your Calendly account:
    Settings -> Integrations -> Webhooks -> Add Webhook Subscription
    """
    try:
        # Get request details for debugging
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Get webhook payload
        body = await request.body()
        webhook_data = json.loads(body)
        
        print(f"\n{'='*60}")
        print(f"📥 Received Calendly webhook:")
        print(f"   Event: {webhook_data.get('event', 'unknown')}")
        print(f"   Time: {webhook_data.get('time', 'unknown')}")
        print(f"   Client IP: {client_ip}")
        print(f"   User-Agent: {user_agent}")
        print(f"   Payload keys: {list(webhook_data.keys())}")
        
        # Process webhook event
        result = await calendly_client.process_webhook_event(webhook_data)
        
        # Return 200 OK to acknowledge receipt
        response_message = result.get("message", "Webhook received but not processed")
        if result.get("processed"):
            response_message = result.get("message", "Webhook processed successfully")
        elif result.get("error"):
            # Include error in message for debugging
            error_msg = result.get("error", "")
            if "404" in error_msg and "TEST" in str(webhook_data.get("payload", {})):
                response_message = "Webhook received successfully! (Test mode: fake URIs detected - this is expected. Real Calendly webhooks will work correctly.)"
            else:
                response_message = f"Webhook received but processing failed: {error_msg}"
        
        return {
            "status": "received",
            "processed": result.get("processed", False),
            "event_type": webhook_data.get("event", ""),
            "message": response_message,
            "test_mode": result.get("test_mode", False)
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in webhook payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        print(f"❌ Error processing webhook: {str(e)}")
        # Still return 200 to prevent Calendly from retrying
        return {
            "status": "error",
            "error": str(e),
            "message": "Webhook received but processing failed"
        }


@app.get("/api/appointments/{booking_id}")
async def get_appointment(booking_id: str):
    """
    Get appointment details by booking ID
    
    This endpoint returns the current status of a booking.
    For pending bookings (TEMP-*), it will check if webhook has confirmed it.
    Also accepts Calendly invitee IDs to fetch bookings directly from Calendly.
    
    Note: TEMP booking IDs are stored in memory. If the server restarts,
    pending bookings will be lost. Once a webhook confirms the booking,
    it's moved to real_bookings and can be found by the temp_booking_id.
    
    For mock mode: Bookings are immediately confirmed.
    For real Calendly API: Bookings start as "pending" until user completes booking in Calendly.
    """
    try:
        print(f"\n📋 Getting appointment: {booking_id}")
        
        # Check if it's a Calendly invitee ID (UUID format)
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        
        if re.match(uuid_pattern, booking_id.lower()):
            # It's a Calendly invitee ID, try to fetch from Calendly
            print(f"📥 Detected Calendly invitee ID: {booking_id}")
            booking = await calendly_client.get_booking_by_invitee_id(booking_id)
            if booking:
                print(f"✅ Found booking via invitee ID")
                return booking
        
        # Try normal booking lookup
        booking = calendly_client.get_booking_by_id(booking_id)
        
        if not booking:
            # Provide helpful error message
            error_detail = {
                "error": "Booking not found",
                "booking_id": booking_id,
                "suggestions": []
            }
            
            # Check if it's a TEMP booking ID
            if booking_id.startswith("TEMP-"):
                error_detail["message"] = (
                    f"Temporary booking ID '{booking_id}' not found. "
                    "This could happen if:\n"
                    "1. The server was restarted (bookings are stored in memory)\n"
                    "2. The booking hasn't been created yet\n"
                    "3. The booking was moved to confirmed status (check by email or Calendly invitee ID)"
                )
                error_detail["suggestions"] = [
                    "Wait for the booking to be confirmed via webhook",
                    "Check your email for Calendly confirmation with invitee ID",
                    "Try searching by Calendly invitee ID if you have it"
                ]
            else:
                error_detail["message"] = f"Booking '{booking_id}' not found in the system."
                error_detail["suggestions"] = [
                    "Verify the booking ID is correct",
                    "Check if the booking was created successfully",
                    "If it's a TEMP booking, wait for webhook confirmation"
                ]
            
            # Include booking statistics for debugging
            error_detail["system_status"] = {
                "pending_bookings_count": len(calendly_client.pending_bookings),
                "confirmed_bookings_count": len(calendly_client.real_bookings),
                "using_mock": calendly_client.use_mock,
                "mock_bookings_count": len(calendly_client.mock_bookings) if hasattr(calendly_client, 'mock_bookings') else 0
            }
            
            raise HTTPException(status_code=404, detail=error_detail)
        
        # Ensure booking_id is included in response
        if "booking_id" not in booking:
            booking["booking_id"] = booking_id
        
        # Add helpful status information
        booking_status = booking.get("status", "unknown")
        is_pending = booking_status == "pending" or booking_id.startswith("TEMP-")
        
        # Add status explanation
        if is_pending and not calendly_client.use_mock:
            booking["status_explanation"] = (
                "This booking is pending confirmation. "
                "Please complete your booking by clicking the scheduling link in your email or the link provided. "
                "Once you complete the booking in Calendly, it will be automatically confirmed via webhook."
            )
            if booking.get("scheduling_link"):
                booking["action_required"] = "Click the scheduling link to complete your booking"
        elif is_pending and calendly_client.use_mock:
            # In mock mode, this shouldn't happen, but handle it
            booking["status"] = "confirmed"
            booking["status_explanation"] = "Booking confirmed (mock mode)"
        
        print(f"✅ Returning booking details (Status: {booking_status}, Mock: {calendly_client.use_mock})")
        return booking
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting appointment {booking_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving booking: {str(e)}")


@app.get("/api/calendly/webhook/status")
async def get_webhook_status():
    """
    Get webhook configuration status and statistics
    
    Returns:
        Webhook status, statistics, and recent events
    """
    try:
        return calendly_client.get_webhook_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendly/webhook/logs")
async def get_webhook_logs(limit: int = 50):
    """
    Get recent webhook event logs
    
    Args:
        limit: Maximum number of logs to return (default: 50, max: 100)
    
    Returns:
        List of webhook event logs
    """
    try:
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 50
        logs = calendly_client.get_webhook_logs(limit=limit)
        return {
            "logs": logs,
            "count": len(logs),
            "total_logs": len(calendly_client.webhook_logs)
        }
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


@app.get("/api/system-prompt/{session_id}")
async def get_system_prompt(session_id: str):
    """
    Get the current system prompt being used for a session
    
    Args:
        session_id: Session identifier
    
    Returns:
        Current system prompt information
    """
    try:
        if session_id not in sessions:
            return {
                "session_id": session_id,
                "system_prompt_type": "main_agent",
                "message": "Session not found. Default prompt will be used."
            }
        
        session = sessions[session_id]
        use_smooth = session.get("use_smooth_prompt", False)
        current_prompt = session.get("current_system_prompt", "")
        
        prompt_type = "smooth_conversation" if use_smooth else "main_agent"
        
        return {
            "session_id": session_id,
            "system_prompt_type": prompt_type,
            "use_smooth_prompt": use_smooth,
            "prompt_preview": current_prompt[:200] + "..." if len(current_prompt) > 200 else current_prompt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendly/test")
async def test_calendly(
    test_availability: bool = False,
    event_type: Optional[str] = None,
    date: Optional[str] = None
):
    """
    Diagnostic endpoint to test Calendly API connectivity and configuration
    
    Args:
        test_availability: If True, also test availability for a specific event type
        event_type: Event type to test availability for (required if test_availability=True)
        date: Date to test availability for in YYYY-MM-DD format (required if test_availability=True)
    
    Returns:
        Diagnostic information about Calendly connection and configuration
    """
    try:
        result = {
            "api_key_configured": bool(calendly_client.api_key),
            "user_url_configured": bool(calendly_client.user_url),
            "using_mock": calendly_client.use_mock,
            "configured_event_types": {}
        }
        
        # Show configured event types
        for key, config in calendly_client.appointment_types.items():
            result["configured_event_types"][key] = {
                "name": config["name"],
                "duration": config["duration"],
                "uuid": config["uuid"]
            }
        
        # Test API connectivity if API key is configured
        if calendly_client.api_key:
            try:
                event_types = await calendly_client.fetch_event_types()
                result["api_connection"] = "success"
                result["calendly_event_types"] = event_types
                result["calendly_event_types_count"] = len(event_types)
                
                # Compare configured UUIDs with actual Calendly event types
                actual_uuids = {et["uuid"] for et in event_types}
                configured_uuids = {config["uuid"] for config in calendly_client.appointment_types.values()}
                
                result["uuid_validation"] = {
                    "configured_uuids": list(configured_uuids),
                    "actual_uuids": list(actual_uuids),
                    "matches": list(configured_uuids & actual_uuids),
                    "missing_in_calendly": list(configured_uuids - actual_uuids),
                    "not_configured": list(actual_uuids - configured_uuids)
                }
                
            except Exception as e:
                result["api_connection"] = "failed"
                result["api_error"] = str(e)
        else:
            result["api_connection"] = "not_configured"
            result["message"] = "CALENDLY_API_KEY not set in environment variables"
        
        # Test availability if requested
        if test_availability:
            if not event_type or not date:
                raise HTTPException(
                    status_code=400,
                    detail="event_type and date parameters are required when test_availability=true"
                )
            
            try:
                # Use availability_tool for better error handling
                availability = await availability_tool.get_available_slots(
                    date=date,
                    appointment_type=event_type
                )
                result["availability_test"] = {
                    "success": True,
                    "date": date,
                    "event_type": event_type,
                    "slots_found": len(availability.get("available_slots", [])),
                    "response": availability,
                    "using_availability_tool": True
                }
            except Exception as e:
                result["availability_test"] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/availability/test")
async def test_availability_tool(
    date: Optional[str] = None,
    appointment_type: str = "consultation",
    time_preference: Optional[str] = None
):
    """
    Test endpoint for the AvailabilityTool
    
    This endpoint helps verify that the availability tool is working correctly
    with the Calendly API integration.
    
    Args:
        date: Date in YYYY-MM-DD format (defaults to tomorrow if not provided)
        appointment_type: Type of appointment to test (default: "consultation")
        time_preference: Optional time preference filter ("morning", "afternoon", "evening")
    
    Returns:
        Test results with detailed information about the availability check
    """
    try:
        # Default to tomorrow if date not provided
        if not date:
            from datetime import timedelta
            tomorrow = datetime.now() + timedelta(days=1)
            date = tomorrow.strftime("%Y-%m-%d")
        
        result = {
            "test_date": date,
            "appointment_type": appointment_type,
            "time_preference": time_preference,
            "calendly_client_status": {
                "api_key_configured": bool(calendly_client.api_key),
                "using_mock": calendly_client.use_mock,
                "user_url_configured": bool(calendly_client.user_url)
            }
        }
        
        # Test availability check
        try:
            availability = await availability_tool.get_available_slots(
                date=date,
                appointment_type=appointment_type,
                time_preference=time_preference
            )
            
            result["availability_check"] = {
                "success": True,
                "slots_found": len(availability.get("available_slots", [])),
                "appointment_type_name": availability.get("appointment_type", ""),
                "has_message": "message" in availability,
                "sample_slots": availability.get("available_slots", [])[:3]  # First 3 slots
            }
            
            if availability.get("message"):
                result["availability_check"]["message"] = availability.get("message")
                
        except Exception as e:
            result["availability_check"] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        # Test date range check (next 3 days)
        try:
            from datetime import timedelta
            start_date = datetime.strptime(date, "%Y-%m-%d")
            end_date = start_date + timedelta(days=2)
            
            range_slots = await availability_tool.get_slots_for_date_range(
                start_date=date,
                end_date=end_date.strftime("%Y-%m-%d"),
                appointment_type=appointment_type,
                max_slots=5,
                time_preference=time_preference
            )
            
            result["date_range_check"] = {
                "success": True,
                "start_date": date,
                "end_date": end_date.strftime("%Y-%m-%d"),
                "slots_found": len(range_slots),
                "sample_slots": range_slots[:3]
            }
        except Exception as e:
            result["date_range_check"] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )