from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, time

class AppointmentType:
    CONSULTATION = "consultation"
    FOLLOWUP = "followup"
    PHYSICAL = "physical"
    SPECIALIST = "specialist"

APPOINTMENT_DURATIONS = {
    AppointmentType.CONSULTATION: 30,
    AppointmentType.FOLLOWUP: 15,
    AppointmentType.PHYSICAL: 45,
    AppointmentType.SPECIALIST: 60,
}

class TimeSlot(BaseModel):
    start_time: str
    end_time: str
    available: bool
    raw_time: Optional[str] = None

class AvailabilityResponse(BaseModel):
    date: str
    available_slots: List[TimeSlot]
    appointment_type: str
    duration_minutes: Optional[int] = None
    message: Optional[str] = None

class PatientInfo(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: str = Field(..., pattern=r'^\+?1?\d{9,15}$')

class BookingRequest(BaseModel):
    appointment_type: str
    date: str
    start_time: str
    patient: PatientInfo
    reason: str = Field(..., min_length=3)

class BookingResponse(BaseModel):
    booking_id: str
    status: str
    confirmation_code: str
    details: dict

class ErrorResponse(BaseModel):
    error: str
    message: str
    suggestions: Optional[List[str]] = None

# Chat-related schemas
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default", description="Session identifier")
    timezone: Optional[str] = Field(default=None, description="User's timezone (e.g., 'America/New_York', 'UTC')")

class ChatResponse(BaseModel):
    message: str
    context: str
    suggestions: Optional[List[str]] = []
    appointment_details: Optional[Dict[str, Any]] = None
    available_slots: Optional[List[Dict[str, Any]]] = None  # Structured slot data for UI

# Appointment request/response schemas (for direct booking)
class AppointmentRequest(BaseModel):
    appointment_type: str
    date: str
    start_time: str
    patient_name: str
    patient_email: EmailStr
    patient_phone: str
    reason: str

class AppointmentResponse(BaseModel):
    booking_id: str
    status: str
    confirmation_code: str
    appointment_type: str
    date: str
    start_time: str
    patient_name: str
    patient_email: str
    clinic_info: Optional[Dict[str, Any]] = None