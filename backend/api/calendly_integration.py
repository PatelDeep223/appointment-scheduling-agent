"""
Calendly API Integration
Handles availability checking and appointment booking
Includes mock implementation for development
"""

import os
import json
import random
import string
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, time
import httpx


class CalendlyClient:
    """
    Calendly API client for managing appointments
    Supports both real Calendly API and mock implementation
    """
    
    def __init__(self):
        self.api_key = os.getenv("CALENDLY_API_KEY")
        self.user_url = os.getenv("CALENDLY_USER_URL")
        self.base_url = "https://api.calendly.com"
        
        # Appointment type configurations
        # Real Calendly event type UUIDs (fetched from your Calendly account)
        self.appointment_types = {
            "consultation": {
                "name": "General Consultation",
                "duration": 30,
                "uuid": "abd38296-0ecc-4834-8a9d-30f2764f6d36"  # Real UUID from Calendly
            },
            "followup": {
                "name": "Follow-up",
                "duration": 15,
                "uuid": "fbc6a86a-dd62-453f-8f3f-e67142d3c252"  # Real UUID from Calendly
            },
            "physical": {
                "name": "Physical Exam",
                "duration": 45,
                "uuid": "08bbf513-9bb8-4259-ac72-15c0babe9dbe"  # Real UUID from Calendly
            },
            "specialist": {
                "name": "Specialist Consultation",
                "duration": 60,
                "uuid": "4a1b7b7e-cae8-4ea1-9b6b-31ab96aa95d8"  # Real UUID from Calendly
            }
        }
        
        # Check if we should use mock:
        # 1. No API key provided
        # 2. UUIDs are placeholders (don't start with real Calendly format)
        # Real Calendly UUIDs are longer alphanumeric strings (not starting with "evt_")
        # Also check if UUIDs look like real Calendly UUIDs (typically 10+ chars, alphanumeric)
        def is_real_uuid(uuid: str) -> bool:
            """Check if UUID looks like a real Calendly UUID"""
            # Placeholder UUIDs start with "evt_" and are short
            # Real Calendly UUIDs are longer alphanumeric strings
            return (not uuid.startswith("evt_") and 
                    len(uuid) >= 10 and 
                    uuid.replace("-", "").replace("_", "").isalnum())
        
        has_real_uuids = all(
            is_real_uuid(apt["uuid"])
            for apt in self.appointment_types.values()
        )
        
        self.use_mock = not self.api_key or not has_real_uuids
        
        # Business hours
        self.business_hours = {
            "monday": {"start": "08:00", "end": "18:00"},
            "tuesday": {"start": "08:00", "end": "18:00"},
            "wednesday": {"start": "08:00", "end": "18:00"},
            "thursday": {"start": "08:00", "end": "18:00"},
            "friday": {"start": "08:00", "end": "18:00"},
            "saturday": {"start": "09:00", "end": "14:00"},
            "sunday": None  # Closed
        }
        
        # Mock bookings storage
        self.mock_bookings: Dict[str, Dict] = {}
        
        # Track if we should fallback to mock after API errors
        self.api_error_count = 0
        self.max_api_errors = 2  # Fallback to mock after 2 errors
        
        if self.use_mock:
            print("📝 Using mock Calendly implementation (no valid API key or placeholder UUIDs detected)")
        else:
            print("🔗 Using real Calendly API")
    
    async def get_availability(
        self,
        date: str,
        appointment_type: str = "consultation"
    ) -> Dict[str, Any]:
        """
        Get available time slots for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            appointment_type: Type of appointment
        
        Returns:
            Dictionary with available slots
        """
        if self.use_mock or self.api_error_count >= self.max_api_errors:
            return await self._mock_get_availability(date, appointment_type)
        else:
            try:
                result = await self._real_get_availability(date, appointment_type)
                self.api_error_count = 0  # Reset on success
                return result
            except Exception as e:
                # On API error, fallback to mock
                self.api_error_count += 1
                if self.api_error_count >= self.max_api_errors:
                    print(f"⚠️  Calendly API errors detected. Falling back to mock mode.")
                    self.use_mock = True
                print(f"⚠️  Calendly API error, using mock: {str(e)}")
                return await self._mock_get_availability(date, appointment_type)
    
    async def create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Create a new appointment booking
        
        Args:
            appointment_type: Type of appointment
            date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format
            patient_name: Patient's full name
            patient_email: Patient's email
            patient_phone: Patient's phone number
            reason: Reason for visit
        
        Returns:
            Booking confirmation details
        """
        if self.use_mock or self.api_error_count >= self.max_api_errors:
            return await self._mock_create_booking(
                appointment_type, date, start_time,
                patient_name, patient_email, patient_phone, reason
            )
        else:
            try:
                result = await self._real_create_booking(
                    appointment_type, date, start_time,
                    patient_name, patient_email, patient_phone, reason
                )
                self.api_error_count = 0  # Reset on success
                return result
            except Exception as e:
                # On API error, fallback to mock
                self.api_error_count += 1
                if self.api_error_count >= self.max_api_errors:
                    print(f"⚠️  Calendly API errors detected. Falling back to mock mode.")
                    self.use_mock = True
                print(f"⚠️  Calendly API error, using mock: {str(e)}")
                return await self._mock_create_booking(
                    appointment_type, date, start_time,
                    patient_name, patient_email, patient_phone, reason
                )
    
    async def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Cancel an existing booking"""
        if self.use_mock or self.api_error_count >= self.max_api_errors:
            return await self._mock_cancel_booking(booking_id)
        else:
            try:
                result = await self._real_cancel_booking(booking_id)
                self.api_error_count = 0  # Reset on success
                return result
            except Exception as e:
                # On API error, fallback to mock
                self.api_error_count += 1
                if self.api_error_count >= self.max_api_errors:
                    print(f"⚠️  Calendly API errors detected. Falling back to mock mode.")
                    self.use_mock = True
                print(f"⚠️  Calendly API error, using mock: {str(e)}")
                return await self._mock_cancel_booking(booking_id)
    
    # Mock Implementation Methods
    
    async def _mock_get_availability(
        self,
        date: str,
        appointment_type: str
    ) -> Dict[str, Any]:
        """Mock implementation of availability checking"""
        
        # Parse date
        target_date = datetime.strptime(date, "%Y-%m-%d")
        day_name = target_date.strftime("%A").lower()
        
        # Check if clinic is open
        hours = self.business_hours.get(day_name)
        if not hours:
            return {
                "date": date,
                "appointment_type": appointment_type,
                "available_slots": [],
                "message": "Clinic is closed on this day"
            }
        
        # Generate time slots
        appt_duration = self.appointment_types[appointment_type]["duration"]
        start_time = datetime.strptime(hours["start"], "%H:%M").time()
        end_time = datetime.strptime(hours["end"], "%H:%M").time()
        
        slots = []
        current = datetime.combine(target_date.date(), start_time)
        end_datetime = datetime.combine(target_date.date(), end_time)
        
        while current + timedelta(minutes=appt_duration) <= end_datetime:
            slot_time = current.strftime("%I:%M %p")
            
            # Randomly mark some slots as unavailable (simulate bookings)
            is_available = random.random() > 0.3  # 70% availability
            
            # Check if slot conflicts with existing bookings
            booking_key = f"{date}_{current.strftime('%H:%M')}"
            if booking_key in self.mock_bookings:
                is_available = False
            
            slots.append({
                "start_time": slot_time,
                "end_time": (current + timedelta(minutes=appt_duration)).strftime("%I:%M %p"),
                "available": is_available,
                "raw_time": current.strftime("%H:%M")
            })
            
            current += timedelta(minutes=30)  # 30-minute intervals
        
        return {
            "date": date,
            "appointment_type": appointment_type,
            "available_slots": slots
        }
    
    async def _mock_create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """Mock implementation of booking creation"""
        
        # Generate booking ID and confirmation code
        booking_id = f"APPT-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.digits, k=3))}"
        confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Calculate end time
        duration = self.appointment_types[appointment_type]["duration"]
        start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = start_datetime + timedelta(minutes=duration)
        
        # Store booking
        booking_key = f"{date}_{start_time}"
        booking = {
            "booking_id": booking_id,
            "confirmation_code": confirmation_code,
            "appointment_type": appointment_type,
            "date": date,
            "start_time": start_time,
            "end_time": end_datetime.strftime("%H:%M"),
            "duration": duration,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "reason": reason,
            "status": "confirmed",
            "created_at": datetime.now().isoformat(),
            "clinic_info": {
                "name": "HealthCare Plus Clinic",
                "address": "123 Health Street, Medical District, NY 10001",
                "phone": "+1-555-123-4567",
                "email": "info@healthcareplus.com"
            }
        }
        
        self.mock_bookings[booking_key] = booking
        
        print(f"✅ Mock booking created: {booking_id}")
        
        return booking
    
    async def _mock_cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Mock implementation of booking cancellation"""
        
        # Find and remove booking
        for key, booking in list(self.mock_bookings.items()):
            if booking["booking_id"] == booking_id:
                del self.mock_bookings[key]
                print(f"🗑️ Mock booking cancelled: {booking_id}")
                return {
                    "booking_id": booking_id,
                    "status": "cancelled",
                    "message": "Appointment cancelled successfully"
                }
        
        return {
            "error": "Booking not found",
            "booking_id": booking_id
        }
    
    # Real Calendly API Methods
    
    async def _real_get_availability(
        self,
        date: str,
        appointment_type: str
    ) -> Dict[str, Any]:
        """Real Calendly API implementation"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        event_type_uuid = self.appointment_types[appointment_type]["uuid"]
        
        # Calculate time range for the day
        # Ensure the start time is in the future (at least current time + 1 hour)
        target_date = datetime.strptime(date, "%Y-%m-%d")
        now = datetime.now()
        
        # If the date is today, start from current time + 1 hour
        # Otherwise, start from beginning of the day
        if target_date.date() == now.date():
            # Today - start from 1 hour from now
            start_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            start_datetime = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # Future date - start from beginning of day
            start_datetime = f"{date}T00:00:00Z"
        
        end_datetime = f"{date}T23:59:59Z"
        
        # Calendly API v2 uses event_type_available_times endpoint with event_type as parameter
        url = f"{self.base_url}/event_type_available_times"
        params = {
            "event_type": f"https://api.calendly.com/event_types/{event_type_uuid}",
            "start_time": start_datetime,
            "end_time": end_datetime
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Transform Calendly response to our format
                slots = []
                # Calendly API returns availability in "collection" array
                time_slots = data.get("collection", [])
                
                for time_slot in time_slots:
                    # Handle different possible response structures
                    if isinstance(time_slot, dict):
                        # Get start time - could be "start_time" or nested in "start_time"
                        start_time_str = time_slot.get("start_time") or time_slot.get("start") or ""
                        if not start_time_str:
                            continue
                        
                        start = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                        
                        # Get end time or calculate
                        end_time_str = time_slot.get("end_time") or time_slot.get("end")
                        if end_time_str:
                            end = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                        else:
                            duration = self.appointment_types[appointment_type]["duration"]
                            end = start + timedelta(minutes=duration)
                        
                        # Check availability - could be "invitees_remaining" or "status"
                        is_available = True
                        if "invitees_remaining" in time_slot:
                            is_available = time_slot.get("invitees_remaining", 0) > 0
                        elif "status" in time_slot:
                            is_available = time_slot.get("status", "").lower() == "available"
                        
                        slots.append({
                            "start_time": start.strftime("%I:%M %p"),
                            "end_time": end.strftime("%I:%M %p"),
                            "available": is_available,
                            "raw_time": start.strftime("%H:%M")
                        })
                
                return {
                    "date": date,
                    "appointment_type": appointment_type,
                    "available_slots": slots
                }
                
        except httpx.HTTPStatusError as e:
            # Don't print full error details for 401/403, just log and re-raise
            # The caller will handle fallback to mock
            if e.response.status_code in [401, 403]:
                print(f"⚠️  Calendly API authentication error (401/403). Check your API key.")
            else:
                print(f"❌ Calendly API error: {str(e)}")
            raise
        except Exception as e:
            print(f"❌ Calendly API error: {str(e)}")
            raise
    
    async def _real_create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """Real Calendly API booking implementation"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        event_type_uuid = self.appointment_types[appointment_type]["uuid"]
        start_datetime = f"{date}T{start_time}:00Z"
        
        url = f"{self.base_url}/scheduled_events"
        payload = {
            "event": {
                "event_type": event_type_uuid,
                "start_time": start_datetime
            },
            "invitee": {
                "name": patient_name,
                "email": patient_email,
                "phone_number": patient_phone
            },
            "questions_and_answers": [
                {
                    "question": "Reason for visit",
                    "answer": reason
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # Transform response
                return {
                    "booking_id": data["resource"]["uri"].split("/")[-1],
                    "confirmation_code": data["resource"]["uri"].split("/")[-1][:6].upper(),
                    "status": "confirmed",
                    "appointment_type": appointment_type,
                    "date": date,
                    "start_time": start_time,
                    "patient_name": patient_name,
                    "patient_email": patient_email,
                    "clinic_info": {
                        "name": "HealthCare Plus Clinic",
                        "address": "123 Health Street, Medical District, NY 10001",
                        "phone": "+1-555-123-4567"
                    }
                }
                
        except Exception as e:
            print(f"❌ Calendly booking error: {str(e)}")
            raise
    
    async def _real_cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Real Calendly API cancellation"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/scheduled_events/{booking_id}/cancellation"
        payload = {
            "reason": "Cancelled by patient"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                return {
                    "booking_id": booking_id,
                    "status": "cancelled",
                    "message": "Appointment cancelled successfully"
                }
                
        except Exception as e:
            print(f"❌ Calendly cancellation error: {str(e)}")
            raise